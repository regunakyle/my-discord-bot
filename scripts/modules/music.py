from discord.ext import commands

from ..utility import Utility as Util
from pathlib import Path
from enum import Enum, auto
import discord, typing as ty, logging, wavelink

logger = logging.getLogger(__name__)


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
        self.bot.loop.create_task(self.connect_nodes())
        # Assume there is only one node: use this for node.get_tracks()
        self.node: wavelink.Node | None = None

    async def isUserBotSameChannel(self, ctx: commands.Context) -> bool:
        """Return True if the user is in the same channel as the bot."""
        vc = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if vc:
            return vc.channel.id == ctx.author.voice.channel.id
        else:
            return False

    async def connect_nodes(self) -> None:
        """Connect to a Lavalink node."""
        await self.bot.wait_until_ready()
        await wavelink.NodePool.create_node(
            bot=self.bot,
            host=Util.getEnvVar("LAVALINK_IP"),
            port=Util.getEnvVar("LAVALINK_PORT"),
            password=Util.getEnvVar("LAVALINK_PASSWORD"),
        )

    @commands.command()
    async def play(self, ctx: commands.Context, *, url: str) -> None:
        """Play a song with the given search query.

        If not connected, connect to our voice channel.
        """

        # User must be in a voice channel
        if not ctx.author.voice:
            await ctx.send("You must be in a voice channel to use this command!")
            return

        # (If the bot is already in a voice channel)
        # The user needs to be in the same voice channel as the bot
        if not await self.isUserBotSameChannel(ctx):
            await ctx.send(
                "You must be in the same voice channel with me to use this command!"
            )
            return

        try:
            track = await self.node.get_tracks(
                query=url,
                cls=wavelink.YouTubeTrack,
            )
            vc: wavelink.Player = (
                ctx.voice_client
                or await ctx.author.voice.channel.connect(cls=wavelink.Player)
            )

            await vc.queue.put_wait(track[0])
            if not vc.is_playing():
                await vc.play(await vc.queue.get_wait())

        except Exception as e:
            print(e)

    @commands.command()
    async def show(self, ctx: commands.Context) -> None:
        """Show all queued songs. Maximum of 10 songs are displayed."""
        if not ctx.voice_client:
            ctx.send("I am not in a voice channel!")
            return
        else:
            vc: wavelink.Player = ctx.voice_client

        # TODO: Find a way to add requester into track object
        embedDict = {
            "title": f"Queue for server {ctx.guild.name}",
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
            embedDict[
                "description"
            ] += f"{index+1}. ({int(item.duration // 60)}:{int(item.duration % 60)}) [{item.title}]({item.uri})\n"
        if vc.is_playing():
            embedDict["fields"][0][
                "value"
            ] = f"[{vc.track.title}]({vc.track.uri}) ({int(vc.track.duration//60)}:{int(vc.track.duration % 60)})"
        await ctx.send(
            embed=discord.Embed.from_dict(embedDict),
            file=discord.File("./assets/images/music.png", filename="music.png"),
        )

    @commands.command()
    async def pause(self, ctx: commands.Context) -> None:
        """Pause the music player if it is playing."""
        if not ctx.voice_client:
            ctx.send("I am not in a voice channel!")
            return
        else:
            vc: wavelink.Player = ctx.voice_client

        if not await self.isUserBotSameChannel(ctx):
            await ctx.send(
                "You must be in the same voice channel with me to use this command!"
            )
            return

        if vc.is_paused():
            await vc.resume()
        else:
            await vc.pause()

    @commands.command()
    async def skip(self, ctx: commands.Context) -> None:
        """Stop and skip the currently playing song."""
        if not ctx.voice_client:
            ctx.send("I am not in a voice channel!")
            return
        else:
            vc: wavelink.Player = ctx.voice_client

        if not await self.isUserBotSameChannel(ctx):
            await ctx.send(
                "You must be in the same voice channel with me to use this command!"
            )
            return

        if vc.is_playing():
            await vc.stop()

    @commands.command()
    async def quit(self, ctx: commands.Context) -> None:
        """Make the bot quit the voice channel. Song queue is cleared."""
        if not ctx.voice_client:
            await ctx.send("I am not in a voice channel!")
            return
        else:
            vc: wavelink.Player = ctx.voice_client

        if not await self.isUserBotSameChannel(ctx):
            await ctx.send(
                "You must be in the same voice channel with me to use this command!"
            )
            return

        vc.queue.reset()
        await vc.disconnect()

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node) -> None:
        """Event fired when a node has finished connecting."""
        self.node = node
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
            await player.channel.send(
                "Something went wrong(?), I will be quitting now..."
            )
            await player.disconnect()
            return

    @commands.Cog.listener()
    async def on_wavelink_track_start(
        self, player: wavelink.Player, track: wavelink.Track
    ) -> None:
        """Event fired after a node started playing a song."""
        # TODO: If no other user presents, quit and clear queue
        if len(player.channel.members) <= 1:
            player.queue.reset()
            await player.channel.send("Quitting because I am alone...")
            await player.disconnect()
            return
        await player.channel.send(f"Now playing *{track.title}*!", delete_after=60)
