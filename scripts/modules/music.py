import asyncio
import logging
import typing as ty
from enum import Enum, auto
from functools import wraps
from pathlib import Path

import discord
import wavelink
from discord.ext import commands, tasks

from ..utility import Utility as Util

logger = logging.getLogger(__name__)

# TODO: Periodically check the count of non-bot members in the same voice channel, quit if it's 0


class REASON(Enum):
    """Enum class for all the possible reasons for stopping the music player."""

    FINISHED = auto()
    STOPPED = auto()
    REPLACED = auto()
    CLEANUP = auto()
    LOAD_FAILED = auto()

    @classmethod
    def get(cls, key: str) -> bool:
        """Return True if key is a member of this class, else return False"""
        try:
            return cls[key]
        except:
            return False


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Assume there is only one node: use this for node.get_tracks()
        self.node: wavelink.Node | None = None
        self.checkNodeConnectionTask.start()

    @tasks.loop(seconds=30)
    async def checkNodeConnectionTask(self) -> None:
        if not self.node:
            await self.create_node()

    async def isUserBotSameChannel(self, ia: discord.Interaction) -> bool:
        """Return True if the user is in the same channel as the bot."""
        vc = discord.utils.get(self.bot.voice_clients, guild=ia.guild)
        if vc:
            return vc.channel.id == ia.user.voice.channel.id
        else:
            return True

    @staticmethod
    def checkNodeDecorator(func: ty.Callable) -> ty.Callable:
        """Check for self.node. If it is None, send error message."""

        @wraps(func)
        async def _wrapper(*args, **kwargs):
            # args[0] is self, args[1] is an discord.Interaction object
            if not args[0].node:
                await args[1].response.send_message(
                    "Music playing server is offline! Please notify the bot owner of the issue!"
                )
            else:
                await func(*args, **kwargs)

        return _wrapper

    async def create_node(self) -> None:
        """Connect to a Lavalink node."""
        await self.bot.wait_until_ready()
        logger.info("Attempting to connect to a node...")
        await wavelink.NodePool.create_node(
            bot=self.bot,
            host=Util.getEnvVar("LAVALINK_IP"),
            port=Util.getEnvVar("LAVALINK_PORT"),
            password=Util.getEnvVar("LAVALINK_PASSWORD"),
        )

    @discord.app_commands.command()
    async def connect_node(
        self,
        ia: discord.Interaction,
    ) -> None:
        """Connect to a new node. Use this if the music player is not working.

        Do NOT use this when the bot is playing music."""

        # Delay response, maximum 15 mins
        await ia.response.defer()

        oldNode = self.node

        await self.create_node()

        # Wait for node update
        while oldNode.identifier == self.node.identifier:
            await asyncio.sleep(0.5)

        await ia.followup.send(
            f"Identifier of old node: <{oldNode.identifier}>\nIdentifier of new node: <{self.node.identifier}>"
        )

    @discord.app_commands.command()
    @discord.app_commands.describe(
        youtube_url="URL of the Youtube video you want to play.",
    )
    @checkNodeDecorator
    async def play(self, ia: discord.Interaction, youtube_url: str) -> None:
        """Play a song with the given search query.

        If not connected, connect to our voice channel.
        """

        # User must be in a voice channel
        if not ia.user.voice:
            await ia.response.send_message(
                "You must be in a voice channel to use this command!"
            )
            return

        # If the bot is already in a voice channel
        # The user needs to be in the same voice channel as the bot
        if not await self.isUserBotSameChannel(ia):
            await ia.response.send_message(
                "You must be in the same voice channel with me to use this command!"
            )
            return

        # Delay response, maximum 15 mins
        await ia.response.defer()

        tracks = await self.node.get_tracks(
            query=youtube_url,
            cls=wavelink.YouTubeTrack,
        )

        if not tracks:
            await ia.followup.send("Your link is invalid!")
            return

        vc: wavelink.Player = (
            ia.guild.voice_client
            or await ia.user.voice.channel.connect(cls=wavelink.Player)
        )

        await vc.queue.put_wait(tracks[0])
        await ia.followup.send(f"Song *{tracks[0].title}* added to queue!")
        if not vc.is_playing():
            await vc.play(await vc.queue.get_wait())

    @discord.app_commands.command()
    @checkNodeDecorator
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
                    "value": len(vc.queue),
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
            ] += f"{index+1}. ({int(item.duration // 60)}:{int(item.duration % 60)}) [{item.title}]({item.uri})\n"
        if vc.is_playing():
            embedDict["fields"][0][
                "value"
            ] = f"[{vc.track.title}]({vc.track.uri}) ({int(vc.track.duration//60)}:{int(vc.track.duration % 60)})"
        await ia.response.send_message(
            embed=discord.Embed.from_dict(embedDict),
            file=discord.File("./assets/images/music.png", filename="music.png"),
        )

    @discord.app_commands.command()
    @checkNodeDecorator
    async def pause(self, ia: discord.Interaction) -> None:
        """Pause the music player if it is playing."""
        if not ia.guild.voice_client:
            await ia.response.send_message("I am not in a voice channel!")
            return
        else:
            vc: wavelink.Player = ia.guild.voice_client

        if not await self.isUserBotSameChannel(ia):
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
    @checkNodeDecorator
    async def skip(self, ia: discord.Interaction) -> None:
        """Stop and skip the currently playing song."""
        if not ia.guild.voice_client:
            await ia.response.send_message("I am not in a voice channel!")
            return
        else:
            vc: wavelink.Player = ia.guild.voice_client

        if not await self.isUserBotSameChannel(ia):
            await ia.response.send_message(
                "You must be in the same voice channel with me to use this command!"
            )
            return

        if vc.is_playing():
            await ia.response.send_message("Skipping the current song...")
            await vc.stop()

    @discord.app_commands.command()
    @checkNodeDecorator
    async def quit(self, ia: discord.Interaction) -> None:
        """Make the bot quit the voice channel. Song queue is also cleared."""
        if not ia.guild.voice_client:
            await ia.response.send_message("I am not in a voice channel!")
            return
        else:
            vc: wavelink.Player = ia.guild.voice_client

        if not await self.isUserBotSameChannel(ia):
            await ia.response.send_message(
                "You must be in the same voice channel with me to use this command!"
            )
            return

        await ia.response.send_message("Ready to leave. Goodbye!")
        vc.queue.reset()
        await vc.disconnect()

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node) -> None:
        """Event fired when a node has finished connecting."""
        self.node = node
        # Forces new Player objects to use this node (hack)
        wavelink.NodePool._nodes = {node.identifier: node}
        logger.info(f"Node: <{node.identifier}> is ready!")

    @commands.Cog.listener()
    async def on_wavelink_track_end(
        self, player: wavelink.Player, track: wavelink.Track, reason
    ) -> None:
        """Event fired when a node has finished playing a song."""

        if REASON.get(reason) in (REASON.FINISHED, REASON.STOPPED):
            if len(player.queue) > 0:
                await player.play(await player.queue.get_wait())
            else:
                player.queue.reset()
                await player.channel.send(
                    "All songs played. Leaving the voice channel..."
                )
                await player.disconnect()
                return
        else:
            player.queue.reset()
            await player.channel.send("Something went wrong, I will be quitting now...")
            await player.disconnect()
            return

    @commands.Cog.listener()
    async def on_wavelink_track_start(
        self, player: wavelink.Player, track: wavelink.Track
    ) -> None:
        """Event fired after a node started playing a song."""
        # If no other non-bot user presents, quit and clear queue
        for member in player.channel.members:
            if not member.bot:
                await player.channel.send(
                    f"Now playing *{track.title}*!", delete_after=30
                )
                return

        player.queue.reset()
        await player.channel.send("Quitting because I am alone...")
        await player.disconnect()
        return
