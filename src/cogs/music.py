import asyncio
import logging
import os
import typing as ty
from functools import wraps

import discord
import wavelink
from discord.client import Client
from discord.ext import commands, tasks
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.cogs._cog_base import CogBase

logger = logging.getLogger(__name__)

# TODO: Refactor


def check_node_exist(func: ty.Callable) -> ty.Callable:
    """Check for connected node. If not found, send error message."""

    @wraps(func)
    async def _wrapper(
        *args: ty.List["Music | discord.Interaction[Client]"],
        **kwargs: ty.Dict[str, ty.Any],
    ) -> None:
        """args[0] is self, args[1] is an discord.Interaction object"""
        interaction: discord.Interaction[Client] = args[1]

        try:
            wavelink.Pool.get_node()
        except wavelink.InvalidNodeException:
            await interaction.response.send_message(
                "Music playing server is offline! Please notify the bot owner of the issue!"
            )
            return

        await func(*args, **kwargs)

    return _wrapper


class Music(CogBase):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ) -> None:
        super().__init__(bot, sessionmaker)
        self.reconnect_count = 0
        self.check_node_connection_task.start()
        self.leave_inactive_voice_channel_task.start()

    ######################################
    # UTILITIES

    async def connect_node(self) -> bool:
        """Connect to a Lavalink node."""
        await self.bot.wait_until_ready()
        logger.info("Attempting to connect to a node...")

        node = wavelink.Node(
            uri=os.getenv("LAVALINK_URL", ""),
            password=os.getenv("LAVALINK_PASSWORD", ""),
            retries=3,
        )
        try:
            await wavelink.Pool.connect(
                client=self.bot,
                nodes=[node],
            )
            await asyncio.sleep(1)

            if node.status == wavelink.NodeStatus.CONNECTED:
                self.reconnect_count = 0
                return True

            return False

        except Exception as e:
            logger.error(e)
            return False

    @tasks.loop(minutes=1)
    async def check_node_connection_task(self) -> None:
        """Discord task: Try to connect to a Lavalink node unless exceeded maximum retries."""
        try:
            wavelink.Pool.get_node()
        except wavelink.InvalidNodeException:
            if self.reconnect_count < 5:
                self.reconnect_count += 1
                await self.connect_node()

    @tasks.loop(minutes=1)
    async def leave_inactive_voice_channel_task(self) -> None:
        """Discord task: Quit if there is no non-bot user in the same voice channel."""
        # Alternative: discord.on_voice_state_update()

        for vc in self.bot.voice_clients:
            # Should be safe to assume this as all voice activity is handled by Wavelink
            vc: wavelink.Player
            alone = True

            for member in vc.channel.members:
                if not member.bot:
                    alone = False
                    break

            if alone:
                await vc.channel.send("Quitting because I am alone...")
                await vc.disconnect()

    async def check_user_bot_same_channel(self, ia: discord.Interaction) -> bool:
        """Return True if the user is in the same channel as the bot."""
        vc: discord.VoiceProtocol = discord.utils.get(
            self.bot.voice_clients, guild=ia.guild
        )
        if vc:
            channel: discord.VoiceChannel | discord.StageChannel = vc.channel
            try:
                return channel.id == ia.user.voice.channel.id
            except Exception:
                return False
        else:
            return True

    # UTILITIES END
    ######################################

    ######################################
    # EVENT LISTENERS

    @commands.Cog.listener()
    async def on_wavelink_node_ready(
        self, payload: wavelink.NodeReadyEventPayload
    ) -> None:
        """Event fired when a node has finished connecting."""
        logger.info(f"Node: <{payload.node.identifier}> is ready!")

    @commands.Cog.listener()
    async def on_wavelink_track_start(
        self, payload: wavelink.TrackStartEventPayload
    ) -> None:
        """Event fired after a node started playing a song."""
        # If no other non-bot user presents, quit and clear queue
        for member in payload.player.channel.members:
            if not member.bot:
                await payload.player.channel.send(
                    "Now playing *{title}*{looping}!".format(
                        title=payload.track.title,
                        looping=" (looping)"
                        if payload.player.queue.mode != wavelink.QueueMode.normal
                        else "",
                    ),
                    delete_after=30,
                )
                return

        await payload.player.channel.send("Quitting because I am alone...")
        await payload.player.disconnect()
        return

    @commands.Cog.listener()
    async def on_wavelink_track_end(
        self, payload: wavelink.TrackEndEventPayload
    ) -> None:
        """Event fired when a node has finished playing a song."""
        if payload.reason.upper() in ("FINISHED", "STOPPED"):
            try:
                track = payload.player.queue.get()
            except wavelink.QueueEmpty:
                await payload.player.channel.send(
                    "All songs played. Leaving the voice channel..."
                )
                await payload.player.disconnect()
                return
            except AttributeError:
                # Most probably because of leave_inactive_voice_channel_task() or quit()
                return

            await asyncio.sleep(1)
            await payload.player.play(track)
        else:
            logger.error(f"Music playing stopped. Reason: {payload.reason.upper()}")
            await payload.player.channel.send(
                "Something went wrong. I will be quitting now..."
            )
            await payload.player.disconnect()
            return

    # EVENT LISTENERS END
    ######################################

    ######################################
    # COMMANDS

    @discord.app_commands.command()
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(
        youtube_url="URL of the Youtube video you want to play.",
    )
    @check_node_exist
    async def play(self, ia: discord.Interaction, youtube_url: str) -> None:
        """Play a song with the given search query."""

        # User must be in a voice channel
        if not ia.user.voice:
            await ia.response.send_message(
                "You must be in a voice channel to use this command!"
            )
            return

        # If the bot is already in a voice channel
        # The user needs to be in the same voice channel as the bot
        if not await self.check_user_bot_same_channel(ia):
            await ia.response.send_message(
                "You must be in the same voice channel with me to use this command!"
            )
            return

        # Delay response, maximum 15 mins
        await ia.response.defer()

        try:
            tracks: ty.List[wavelink.Playable] = await wavelink.Playable.search(
                youtube_url
            )
        except wavelink.LavalinkLoadException:
            await ia.followup.send("Your link is invalid!")
            return

        if isinstance(tracks, wavelink.Playlist):
            # Convert wavelink.Playlist to ty.List[wavelink.Playable]
            tracks = [tracks.tracks[tracks.selected if tracks.selected >= 0 else 0]]

        vc: wavelink.Player = (
            ia.guild.voice_client
            or await ia.user.voice.channel.connect(cls=wavelink.Player)
        )

        track = tracks[0]
        # Add requester name to track, so that the `queue` command can show it
        track.extras = {"requester": ia.user.name}

        await vc.queue.put_wait(track)
        await ia.followup.send(
            f"Song *{track.title}* added to queue!"
            + (
                f"\n(Note: Currently looping *{vc.current.title}*)"
                if vc.queue.mode != wavelink.QueueMode.normal
                else ""
            )
        )
        if not vc.playing:
            await vc.play(vc.queue.get())

    @discord.app_commands.command()
    @discord.app_commands.guild_only()
    @check_node_exist
    async def queue(self, ia: discord.Interaction) -> None:
        """Show all queued songs. A maximum of 20 songs are displayed."""
        if not ia.guild.voice_client:
            await ia.response.send_message("I am not in a voice channel!")
            return
        else:
            vc: wavelink.Player = ia.guild.voice_client

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
                    "value": len(vc.queue) if len(vc.queue) else "Empty",
                    "inline": True,
                },
                {
                    "name": "Paused",
                    "value": vc.paused,
                    "inline": True,
                },
                {
                    "name": "Looping",
                    "value": vc.queue.mode != wavelink.QueueMode.normal,
                    "inline": True,
                },
            ],
        }

        for index, queue_track in enumerate(vc.queue):
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
                "{index}. [{title}]({url})\n({minutes}:{seconds} - requested by {user})\n".format(
                    index=index + 1,
                    title=queue_track.title,
                    url=queue_track.uri,
                    minutes=int(vc.current.length / 1000 // 60),
                    seconds=int(queue_track.length / 1000 % 60),
                    user=dict(queue_track.extras)["requester"],
                )
            )

        if vc.playing:
            embedDict["description"] = (
                "**__CURRENTLY PLAYING__**\n[{title}]({url})\n({minutes}:{seconds} - requested by {user})".format(
                    title=vc.current.title,
                    url=vc.current.uri,
                    minutes=int(vc.current.length / 1000 // 60),
                    seconds=int(vc.current.length / 1000 % 60),
                    user=dict(vc.current.extras)["requester"],
                )
            )

        await ia.response.send_message(
            embed=discord.Embed.from_dict(embedDict),
            file=discord.File("./assets/images/music.png", filename="music.png"),
        )

    @discord.app_commands.command()
    @discord.app_commands.guild_only()
    @check_node_exist
    async def pause(self, ia: discord.Interaction) -> None:
        """Pause or unpause the music player."""
        if not ia.guild.voice_client:
            await ia.response.send_message("I am not in a voice channel!")
            return
        else:
            vc: wavelink.Player = ia.guild.voice_client

        if not await self.check_user_bot_same_channel(ia):
            await ia.response.send_message(
                "You must be in the same voice channel with me to use this command!"
            )
            return

        if vc.paused:
            await vc.pause(False)
            await ia.response.send_message("Music player resumed!")
        else:
            await vc.pause(True)
            await ia.response.send_message("Music player paused!")

    @discord.app_commands.command()
    @discord.app_commands.guild_only()
    @check_node_exist
    async def loop(self, ia: discord.Interaction) -> None:
        """Loop the current playing song. Use again to cancel looping."""
        if not ia.guild.voice_client:
            await ia.response.send_message("I am not in a voice channel!")
            return
        else:
            vc: wavelink.Player = ia.guild.voice_client

        if not await self.check_user_bot_same_channel(ia):
            await ia.response.send_message(
                "You must be in the same voice channel with me to use this command!"
            )
            return

        if vc.playing:
            if vc.queue.mode == wavelink.QueueMode.normal:
                vc.queue.mode = wavelink.QueueMode.loop
                await ia.response.send_message(
                    "Looping started. Run /loop again to cancel..."
                )
                return
            else:
                vc.queue.mode = wavelink.QueueMode.normal
                await ia.response.send_message("Looping stopped.")
                return
        else:
            await ia.response.send_message("I am not playing any music!")

    @discord.app_commands.command()
    @discord.app_commands.guild_only()
    @check_node_exist
    async def skip(self, ia: discord.Interaction) -> None:
        """Stop and skip the currently playing song. Also untoggles looping."""
        if not ia.guild.voice_client:
            await ia.response.send_message("I am not in a voice channel!")
            return
        else:
            vc: wavelink.Player = ia.guild.voice_client

        if not await self.check_user_bot_same_channel(ia):
            await ia.response.send_message(
                "You must be in the same voice channel with me to use this command!"
            )
            return

        if vc.playing:
            await ia.response.send_message(
                "Skipping the current song. {looping}".format(
                    looping="Looping stopped."
                    if vc.queue.mode != wavelink.QueueMode.normal
                    else ""
                )
            )
            vc.queue.mode = wavelink.QueueMode.normal
            await vc.stop()

    @discord.app_commands.command()
    @discord.app_commands.guild_only()
    @check_node_exist
    async def quit(self, ia: discord.Interaction) -> None:
        """Make the bot quit the voice channel. Song queue is also cleared."""
        if not ia.guild.voice_client:
            await ia.response.send_message("I am not in a voice channel!")
            return
        else:
            vc: wavelink.Player = ia.guild.voice_client

        if not await self.check_user_bot_same_channel(ia):
            await ia.response.send_message(
                "You must be in the same voice channel with me to use this command!"
            )
            return

        await ia.response.send_message("Ready to leave. Goodbye!")
        await vc.disconnect()

    @discord.app_commands.command()
    @discord.app_commands.guild_only()
    async def connect_music(
        self,
        ia: discord.Interaction,
    ) -> None:
        """(OWNER ONLY) Use this if the music player is not working.

        Do NOT use this when the bot is playing music."""

        if not await self.bot.is_owner(ia.user):
            await ia.response.send_message("Only the bot owner may use this command!")
            return

        # Delay response, maximum 15 mins
        await ia.response.defer()

        if await self.connect_node():
            await ia.followup.send("Connection successful.")
            return

        await ia.followup.send("Reconnection failed.")
