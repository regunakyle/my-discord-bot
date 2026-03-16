import logging
import os
import re
import typing as ty
from urllib.parse import urlparse

import discord
import discord.types
import discord.types.voice
import lavalink
import lavalink.common
from discord import app_commands
from discord.client import Client
from discord.ext import commands, tasks
from lavalink.errors import ClientError
from lavalink.events import (
    NodeDisconnectedEvent,
    NodeReadyEvent,
    QueueEndEvent,
    TrackLoadFailedEvent,
    TrackStartEvent,
)
from lavalink.player import DefaultPlayer
from lavalink.server import LoadType
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ._cog_base import CogBase

logger = logging.getLogger(__name__)
url_rx = re.compile(r"https?://(?:www\.)?.+")


async def create_player_check(ia: discord.Interaction[Client]) -> ty.Literal[True]:
    """
    A check that is invoked before any commands marked with `@app_commands.check(create_player)` can run.

    This function will try to create a player for the guild associated with this Context, or raise
    an error which will be relayed to the user if one cannot be created.
    """

    if ia.guild is None:
        raise app_commands.NoPrivateMessage()

    player = ty.cast(
        lavalink.Client[DefaultPlayer], ia.client.lavalink
    ).player_manager.create(ia.guild.id)

    should_connect = ia.command.name in ("play", "pause", "loop", "skip", "quit")

    voice_client = ia.guild.voice_client

    if not ia.user.voice or not ia.user.voice.channel:
        # Check if we're in a voice channel. If we are, tell the user to join our voice channel.
        if voice_client is not None:
            raise Exception("You need to join my voice channel first!")

        # Otherwise, tell them to join any voice channel to begin playing music.
        raise Exception("Join a voice channel first!")

    voice_channel = ia.user.voice.channel

    if voice_client is None:
        if not should_connect:
            raise Exception("I'm not in a voice channel! Use `/play` to play a song.")

        permissions = voice_channel.permissions_for(ia.guild.me)

        if not permissions.connect or not permissions.speak:
            raise Exception(
                "I need the `CONNECT` and `SPEAK` permissions; Please notify admins!"
            )

        if voice_channel.user_limit > 0:
            # A limit of 0 means no limit. Anything higher means that there is a member limit which we need to check.
            # If it's full, and we don't have "move members" permissions, then we cannot join it.
            if (
                len(voice_channel.members) >= voice_channel.user_limit
                and not ia.guild.me.guild_permissions.move_members
            ):
                raise Exception("Your voice channel is full!")

        player.store("channel", ia.channel.id)
        await ia.user.voice.channel.connect(cls=LavalinkVoiceClient)

    elif voice_client.channel.id != voice_channel.id:
        raise Exception("You need to be in my voice channel to use this command!")

    return True


class LavalinkVoiceClient(discord.VoiceProtocol):
    """
    This is the preferred way to handle external voice sending
    This client will be created via a cls in the connect method of the channel
    see the following documentation:
    https://discordpy.readthedocs.io/en/latest/api.html#voiceprotocol
    """

    def __init__(
        self, client: discord.Client, channel: discord.abc.Connectable
    ) -> None:
        self.client = client
        self.channel: discord.VoiceChannel | discord.StageChannel = channel
        self.guild_id = self.channel.guild.id
        self._destroyed = False

        # Create a shortcut to the Lavalink client here.
        # (Should be created in the __init__ of music cog)
        self.lavalink: lavalink.Client[DefaultPlayer] = self.client.lavalink

    async def on_voice_server_update(
        self, data: discord.types.voice.VoiceServerUpdate
    ) -> None:
        # the data needs to be transformed before being handed down to
        # voice_update_handler
        lavalink_data: lavalink.common.VoiceServerUpdatePayload = {
            "t": "VOICE_SERVER_UPDATE",
            "d": ty.cast(lavalink.common.VoiceServerUpdateData, data),
        }
        await self.lavalink.voice_update_handler(lavalink_data)

    async def on_voice_state_update(
        self, data: discord.types.voice.GuildVoiceState
    ) -> None:
        channel_id = data["channel_id"]

        if not channel_id:
            await self._destroy()
            return

        self.channel = self.client.get_channel(int(channel_id))

        # the data needs to be transformed before being handed down to
        # voice_update_handler
        lavalink_data: lavalink.common.VoiceStateUpdatePayload = {
            "t": "VOICE_STATE_UPDATE",
            "d": ty.cast(lavalink.common.VoiceStateUpdateData, data),
        }

        await self.lavalink.voice_update_handler(lavalink_data)

    async def connect(
        self,
        *,
        timeout: float,
        reconnect: bool,
        self_deaf: bool = False,
        self_mute: bool = False,
    ) -> None:
        """
        Connect the bot to the voice channel and create a player_manager
        if it doesn't exist yet.
        """

        # ensure there is a player_manager when creating a new voice_client
        self.lavalink.player_manager.create(guild_id=self.channel.guild.id)
        await self.channel.guild.change_voice_state(
            channel=self.channel, self_mute=self_mute, self_deaf=self_deaf
        )

    async def disconnect(self, *, force: bool = False) -> None:
        """
        Handles the disconnect.
        Cleans up running player and leaves the voice client.
        """

        player = self.lavalink.player_manager.get(self.channel.guild.id)

        # no need to disconnect if we are not connected
        if not force and not player.is_connected:
            return

        # None means disconnect
        await self.channel.guild.change_voice_state(channel=None)

        # update the channel_id of the player to None
        # this must be done because the on_voice_state_update that would set channel_id
        # to None doesn't get dispatched after the disconnect
        player.channel_id = None
        await self._destroy()

    async def _destroy(self) -> None:
        self.cleanup()

        if self._destroyed:
            # Idempotency handling, if `disconnect()` is called, the changed voice state
            # could cause this to run a second time.
            return

        self._destroyed = True

        try:
            await self.lavalink.player_manager.destroy(self.guild_id)
        except ClientError:
            pass


class Music(CogBase):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ) -> None:
        super().__init__(bot, sessionmaker)

        if not os.getenv("LAVALINK_URL"):
            raise Exception("LAVALINK_URL is not set, cannot initialize lavalink")

        parsed_url = urlparse(os.getenv("LAVALINK_URL"))

        if not hasattr(bot, "lavalink"):
            bot.lavalink = lavalink.Client(bot.user.id)
            bot.lavalink.add_node(
                host=f"{parsed_url.hostname}{parsed_url.path}",
                port=parsed_url.port
                if parsed_url.port
                else 443
                if parsed_url.scheme in ("https", "wss")
                else 80,
                password=os.getenv("LAVALINK_PASSWORD", "youshallnotpass"),
                region="hk",
                name="default-node",
            )

        self.bot = bot
        # Create a shortcut to the Lavalink client here.
        self.lavalink: lavalink.Client[DefaultPlayer] = bot.lavalink

        self.lavalink.add_event_hooks(self)
        self.leave_inactive_voice_channel_task.start()

    # region UTILITIES

    @tasks.loop(minutes=1)
    async def leave_inactive_voice_channel_task(self) -> None:
        """Discord task: Quit if there is no non-bot user in the same voice channel."""

        for vc in self.bot.voice_clients:
            vc: LavalinkVoiceClient

            for member in vc.channel.members:
                if not member.bot:
                    return

            await vc.channel.send("Quitting because I am alone...")
            await vc.disconnect()

    # endregion UTILITIES

    # region EVENT LISTENERS

    @lavalink.listener(TrackStartEvent)
    async def on_track_start(self, event: TrackStartEvent) -> None:
        """Event fired after a node started playing a song."""

        guild_id = event.player.guild_id
        channel_id = event.player.channel_id
        guild = self.bot.get_guild(guild_id)

        if not guild:
            return await self.lavalink.player_manager.destroy(guild_id)

        channel = guild.get_channel(channel_id)

        if channel:
            await channel.send(
                "Now playing: {} by {}".format(event.track.title, event.track.author)
            )

    @lavalink.listener(QueueEndEvent)
    async def on_queue_end(self, event: QueueEndEvent) -> None:
        """Event fired when there are no more tracks in the queue."""

        guild_id = event.player.guild_id
        guild = self.bot.get_guild(guild_id)

        if guild is not None:
            logger.info(f"Queue finished for guild: {guild_id}")
            await guild.voice_client.disconnect(force=True)

    @lavalink.listener(TrackLoadFailedEvent)
    async def on_track_load_fail(self, event: TrackLoadFailedEvent) -> None:
        """Event fired when a deferred audio track fails to produce a playable track."""

        logger.warning(f"Track load failed: {event.original}")

        # There is only DefaultPlayer implementation for BasePlayer
        await ty.cast(lavalink.DefaultPlayer, event.player).skip()

    @lavalink.listener(NodeReadyEvent)
    async def on_node_connect(self, event: NodeReadyEvent) -> None:
        """Event fired when a node has finished connecting."""

        logger.info(f"Node: <{event.node.name}> is ready!")

    @lavalink.listener(NodeDisconnectedEvent)
    async def on_node_disconnect(self, event: NodeDisconnectedEvent) -> None:
        """Event fired when the connection to a Lavalink node drops and becomes unavailable."""

        logger.error(
            f"Node: <{event.node.name}> disconnected! Code: {event.code}, Reason: {event.reason}"
        )

    # endregion EVENT LISTENERS

    # region COMMANDS

    @discord.app_commands.command()
    @discord.app_commands.describe(query="URL of the Youtube video you want to play.")
    @discord.app_commands.check(create_player_check)
    async def play(self, ia: discord.Interaction, query: str) -> None:
        """Searches and plays a song from a given query."""

        await ia.response.defer()

        # Get the player for this guild from cache.
        player = self.lavalink.player_manager.get(ia.guild.id)

        # Check if the user input might be a URL. If it isn't, we can Lavalink do a YouTube search for it instead.
        # SoundCloud searching is possible by prefixing "scsearch:" instead.
        if not url_rx.match(query):
            query = f"ytsearch:{query}"

        # Get the results for the query from Lavalink.
        results = await player.node.get_tracks(query)

        embed = discord.Embed(color=discord.Color.blurple())

        # Valid load_types are:
        #   TRACK    - direct URL to a track
        #   PLAYLIST - direct URL to playlist
        #   SEARCH   - query prefixed with either "ytsearch:" or "scsearch:". This could possibly be expanded with plugins.
        #   EMPTY    - no results for the query (result.tracks will be empty)
        #   ERROR    - the track encountered an exception during loading
        if results.load_type == LoadType.EMPTY:
            return await ia.followup.send("I couldn'\t find any tracks for that query.")
        elif results.load_type == LoadType.PLAYLIST:
            tracks = results.tracks

            # Add all of the tracks from the playlist to the queue.
            for track in tracks:
                track.extra["requester"] = ia.user.name
                player.add(track=track)

            embed.title = "Playlist Enqueued!"
            embed.description = f"{results.playlist_info.name} - {len(tracks)} tracks"
        else:
            track = results.tracks[0]
            embed.title = "Track Enqueued!"
            embed.description = f"[{track.title}]({track.uri})"

            track.extra["requester"] = ia.user.name

            player.add(track=track)

        await ia.followup.send(embed=embed)

        # We don't want to call .play() if the player is playing as that will effectively skip
        # the current track.
        if not player.is_playing:
            await player.play()

    @discord.app_commands.command()
    @discord.app_commands.check(create_player_check)
    async def quit(self, ia: discord.Interaction) -> None:
        """Make the bot quit the voice channel. Song queue is also cleared."""

        player = self.lavalink.player_manager.get(ia.guild.id)
        # The necessary voice channel checks are handled in "create_player."
        # We don't need to duplicate code checking them again.

        # Clear the queue to ensure old tracks don't start playing
        # when someone else queues something.
        player.queue.clear()
        # Stop the current track so Lavalink consumes less resources.
        await player.stop()
        # Disconnect from the voice channel.
        await ia.guild.voice_client.disconnect(force=True)

        await ia.response.send_message("Ready to leave. Goodbye!")

    @discord.app_commands.command()
    @discord.app_commands.check(create_player_check)
    async def queue(self, ia: discord.Interaction) -> None:
        """Show all queued songs. A maximum of 20 songs are displayed."""
        player: lavalink.DefaultPlayer = self.lavalink.player_manager.get(ia.guild.id)

        embedDict: ty.Dict[
            str, str | int | ty.Dict[str, str] | ty.List[ty.Dict[str, str | int | bool]]
        ] = {
            "title": f"Queue for server {ia.guild.name}",
            "description": "",
            "color": 65535,
            "thumbnail": {"url": "attachment://music.png"},
            "fields": [
                {
                    "name": "Queue size",
                    "value": len(player.queue) if len(player.queue) else "Empty",
                    "inline": True,
                },
                {
                    "name": "Paused",
                    "value": player.paused,
                    "inline": True,
                },
                {
                    "name": "Looping",
                    "value": player.loop == player.LOOP_SINGLE,
                    "inline": True,
                },
            ],
        }

        for index, queue_track in enumerate(player.queue):
            if index >= 20:
                # TODO: Pagination
                break

            if index == 0:
                embedDict["fields"].insert(
                    0,
                    {
                        "name": "**__ON QUEUE__**",
                        "value": "",
                        "inline": False,
                    },
                )

            embedDict["fields"][0]["value"] += (
                "{index}. [{title}]({url})\n({minutes:02d}:{seconds:02d} - requested by {user})\n".format(
                    index=index + 1,
                    title=queue_track.title,
                    url=queue_track.uri,
                    minutes=int(player.current.duration / 1000 // 60),
                    seconds=int(queue_track.duration / 1000 % 60),
                    user=dict(queue_track.extra)["requester"],
                )
            )

        if player.is_playing:
            embedDict["description"] = (
                "**__CURRENTLY PLAYING__**\n[{title}]({url})\n({minutes:02d}:{seconds:02d} - requested by {user})".format(
                    title=player.current.title,
                    url=player.current.uri,
                    minutes=int(player.current.duration / 1000 // 60),
                    seconds=int(player.current.duration / 1000 % 60),
                    user=dict(player.current.extra)["requester"],
                )
            )

        await ia.response.send_message(
            embed=discord.Embed.from_dict(embedDict),
            file=discord.File("./assets/images/music.png", filename="music.png"),
        )

    @discord.app_commands.command()
    @discord.app_commands.check(create_player_check)
    async def pause(self, ia: discord.Interaction) -> None:
        """Pause or unpause the music player."""
        player: lavalink.DefaultPlayer = self.lavalink.player_manager.get(ia.guild.id)

        if player.paused:
            await player.set_pause(False)
            await ia.response.send_message("Music player resumed!")
        else:
            await player.set_pause(True)
            await ia.response.send_message("Music player paused!")

    @discord.app_commands.command()
    @discord.app_commands.check(create_player_check)
    async def loop(self, ia: discord.Interaction) -> None:
        """Loop the current playing song. Run again to cancel looping."""
        player: lavalink.DefaultPlayer = self.lavalink.player_manager.get(ia.guild.id)

        if player.loop == player.LOOP_NONE:
            player.set_loop(player.LOOP_SINGLE)
            await ia.response.send_message(
                "Looping started. Run /loop again to cancel..."
            )
        else:
            player.set_loop(player.LOOP_NONE)
            await ia.response.send_message("Looping stopped.")

    @discord.app_commands.command()
    @discord.app_commands.check(create_player_check)
    async def skip(self, ia: discord.Interaction) -> None:
        """Stop and skip the currently playing song. Also untoggles looping."""
        player: lavalink.DefaultPlayer = self.lavalink.player_manager.get(ia.guild.id)

        await ia.response.send_message(
            "Skipping the current song.{looping}".format(
                looping=" Looping stopped." if player.loop != player.LOOP_NONE else ""
            )
        )
        player.set_loop(player.LOOP_NONE)
        await player.skip()

    # endregion COMMANDS
