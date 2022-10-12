from discord.ext import commands

from symbol import pass_stmt
from ..utility import Utility as Util
from pathlib import Path
from enum import Enum, auto
import discord, typing as ty, logging, asyncio, wavelink

logger = logging.getLogger(__name__)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self.connect_nodes())
        self.musicQueue = {}
        for guild in self.bot.guilds:
            self.musicQueue[guild.id] = wavelink.Queue(max_size=20)

    class REASON(Enum):
        FINISHED = auto()
        STOPPED = auto()
        REPLACED = auto()
        # CLEANUP = auto()
        # LOAD_FAILED = auto()

        @classmethod
        def get(cls, key: str) -> bool:
            """Return True if key is a member of the enum, else return False"""
            try:
                return cls[key]
            except:
                return False

    async def connect_nodes(self):
        """Connect to our Lavalink nodes."""
        await self.bot.wait_until_ready()
        await wavelink.NodePool.create_node(
            bot=self.bot, host="localhost", port=2333, password="youshallnotpass"
        )

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        """Event fired when a node has finished connecting."""
        print(f"Node: <{node.identifier}> is ready!")

    @commands.Cog.listener()
    async def on_wavelink_track_end(
        self, player: wavelink.Player, track: wavelink.Track, reason
    ):
        """Event fired when a node has finished playing a song."""
        if self.REASON.get(reason) == self.REASON.FINISHED:
            print(player.channel.id)
        elif self.REASON.get(reason) == self.REASON.STOPPED:
            pass
        elif self.REASON.get(reason) == self.REASON.REPLACED:
            pass
        else:
            pass
            # Raise error

    @commands.Cog.listener()
    async def on_wavelink_track_start(
        self, player: wavelink.Player, track: wavelink.Track
    ):
        """Event fired when a node has finished connecting."""
        print(player.channel.id)

    @commands.command()
    async def play(self, ctx: commands.Context, *, url: str):
        """Play a song with the given search query.

        If not connected, connect to our voice channel.
        """
        if not (ctx.author.id in [263243377821089792, 874293484230676591]):
            return

        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(
                cls=wavelink.Player
            )
        else:
            vc: wavelink.Player = ctx.voice_client

        # get node from nodepool, then get tracks
        track = await vc.node.get_tracks(
            query=url,
            cls=wavelink.YouTubeTrack,
        )

        if len(track) == 0:
            await vc.disconnect()
            return

        await vc.play(track[0])
        while vc.is_connected():
            # CHECKING
            await asyncio.sleep(1)
            if not vc.is_playing():
                await vc.disconnect()

    @commands.command()
    async def queue(self, ctx: commands.Context, *, url: str):
        """queue"""
        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(
                cls=wavelink.Player
            )
        else:
            vc: wavelink.Player = ctx.voice_client

        track = await vc.node.get_tracks(
            query=url,
            cls=wavelink.YouTubeTrack,
        )

        if len(track) == 0:
            await vc.disconnect()
            return

        self.musicQueue[vc.guild.id].put(track[0])

    @commands.command()
    async def show(self, ctx: commands.Context):
        """show"""

        await ctx.send(self.musicQueue[ctx.guild.id])

    @commands.command()
    async def pause(self, ctx: commands.Context):
        """QUIT"""
        if not ctx.voice_client:
            return
        else:
            vc: wavelink.Player = ctx.voice_client

        await vc.pause()

    @commands.command()
    async def resume(self, ctx: commands.Context):
        """resume"""
        if not ctx.voice_client:
            return
        else:
            vc: wavelink.Player = ctx.voice_client

        await vc.resume()

    @commands.command()
    async def skip(self, ctx: commands.Context):
        """skip"""
        pass

    @commands.command()
    async def quit(self, ctx: commands.Context):
        """quit"""
        if not ctx.voice_client:
            await ctx.s("Fuck off")
        else:
            vc: wavelink.Player = ctx.voice_client

        await vc.disconnect()
