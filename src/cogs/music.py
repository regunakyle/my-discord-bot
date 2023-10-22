import logging
import os
import typing as ty
from functools import wraps

import discord
import wavelink
from discord.ext import commands, tasks
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .cog_base import CogBase

logger = logging.getLogger(__name__)

# TODO: Periodically check the count of non-bot members in the same voice channel, quit if it's 0


def check_node_exist(func: ty.Callable) -> ty.Callable:
    """Check for connected node. If not found, send error message."""

    @wraps(func)
    async def _wrapper(*args: ty.List[ty.Any], **kwargs: ty.Dict[str, ty.Any]) -> None:
        # args[0] is self, args[1] is an discord.Interaction object
        try:
            wavelink.NodePool.get_connected_node()
        except wavelink.InvalidNode:
            await args[1].response.send_message(
                "Music playing server is offline! Please notify the bot owner of the issue!"
            )
            return

        await func(*args, **kwargs)

    return _wrapper


class Music(CogBase):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ):
        super().__init__(bot, sessionmaker)
        self.reconnect_count = 0
        self.check_node_connection_task.start()

    ######################################
    # UTILITIES

    async def connect_node(self) -> None:
        """Connect to a Lavalink node."""
        await self.bot.wait_until_ready()
        logger.info("Attempting to connect to a node...")
        await wavelink.NodePool.connect(
            client=self.bot,
            nodes=[
                wavelink.Node(
                    uri=f'{os.getenv("LAVALINK_IP")}:{os.getenv("LAVALINK_PORT")}',
                    password=os.getenv("LAVALINK_PASSWORD", ""),
                    # use_http=True,
                    retries=3,
                )
            ],
        )

    @tasks.loop(minutes=1)
    async def check_node_connection_task(self) -> None:
        try:
            wavelink.NodePool.get_connected_node()
        except wavelink.InvalidNode:
            if self.reconnect_count < 5:
                self.reconnect_count += 1
                await self.connect_node()

    async def check_user_bot_same_channel(self, ia: discord.Interaction) -> bool:
        """Return True if the user is in the same channel as the bot."""
        vc: discord.VoiceProtocol = discord.utils.get(
            self.bot.voice_clients, guild=ia.guild
        )
        if vc:
            try:
                return vc.channel.id == ia.user.voice.channel.id
            except:
                return False
        else:
            return True

    # UTILITIES END
    ######################################

    ######################################
    # EVENT LISTENERS

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node) -> None:
        """Event fired when a node has finished connecting."""
        logger.info(f"Node: <{node.id}> is ready!")

    @commands.Cog.listener()
    async def on_wavelink_track_start(
        self, payload: wavelink.TrackEventPayload
    ) -> None:
        """Event fired after a node started playing a song."""
        # If no other non-bot user presents, quit and clear queue
        for member in payload.player.channel.members:
            if not member.bot:
                await payload.player.channel.send(
                    f"Now playing *{payload.track.title}*!", delete_after=30
                )
                return

        payload.player.queue.reset()
        await payload.player.channel.send("Quitting because I am alone...")
        await payload.player.disconnect()
        return

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEventPayload) -> None:
        """Event fired when a node has finished playing a song."""
        if payload.reason.upper() in ("FINISHED", "STOPPED"):
            if len(payload.player.queue) > 0:
                await payload.player.play(await payload.player.queue.get_wait())
            else:
                payload.player.queue.reset()
                await payload.player.channel.send(
                    "All songs played. Leaving the voice channel..."
                )
                await payload.player.disconnect()
                return
        else:
            payload.player.queue.reset()
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

        tracks: ty.List[wavelink.Playable] = await wavelink.YouTubeTrack.search(
            youtube_url
        )

        if not tracks:
            await ia.followup.send("Your link is invalid!")
            return

        if isinstance(tracks, wavelink.YouTubePlaylist):
            tracks = [
                tracks.tracks[
                    tracks.selected_track if tracks.selected_track >= 0 else 0
                ]
            ]

        vc: wavelink.Player = (
            ia.guild.voice_client
            or await ia.user.voice.channel.connect(cls=wavelink.Player)
        )

        await vc.queue.put_wait(tracks[0])
        await ia.followup.send(f"Song *{tracks[0].title}* added to queue!")
        if not vc.is_playing():
            await vc.play(await vc.queue.get_wait())

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

        # TODO: Find a way to add requester into track object
        embedDict = {
            "title": f"Queue for server {ia.guild.name}",
            "description": "",
            "color": 65535,
            "thumbnail": {"url": "attachment://music.png"},
            "fields": [
                {
                    "name": "Currently playing",
                    "value": "Not playing anything :)",
                    "inline": False,
                },
                {
                    "name": "Total queue size",
                    "value": len(vc.queue) + 1,
                    "inline": True,
                },
                {
                    "name": "Paused",
                    "value": vc.is_paused(),
                    "inline": True,
                },
                {
                    "name": "Playing in",
                    "value": vc.channel.name,
                    "inline": True,
                },
            ],
        }
        for index, item in enumerate(vc.queue):
            if index >= 20:
                break
            embedDict[
                "description"
            ] += f"{index+1}. ({int(item.duration / 1000 // 60)}:{int(item.duration / 1000 % 60)}) [{item.title}]({item.uri})\n"
        if vc.is_playing():
            embedDict["fields"][0][
                "value"
            ] = f"[{vc.current.title}]({vc.current.uri}) ({int(vc.current.duration / 1000 // 60)}:{int(vc.current.duration / 1000 % 60)})"
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

        if vc.is_paused():
            await vc.resume()
            await ia.response.send_message("Music player resumed!")
        else:
            await vc.pause()
            await ia.response.send_message("Music player paused!")

    @discord.app_commands.command()
    @discord.app_commands.guild_only()
    @check_node_exist
    async def skip(self, ia: discord.Interaction) -> None:
        """Stop and skip the currently playing song."""
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

        if vc.is_playing():
            await ia.response.send_message("Skipping the current song...")
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
        vc.queue.reset()
        await vc.disconnect()
