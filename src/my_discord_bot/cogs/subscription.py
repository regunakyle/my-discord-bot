import logging
import os
import typing as ty

import discord
import googleapiclient.discovery
import googleapiclient.errors
from discord.ext import commands, tasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models import Guild
from ._cog_base import CogBase

if ty.TYPE_CHECKING:
    from googleapiclient._apis.youtube.v3 import YouTubeResource

logger = logging.getLogger(__name__)


class Subscription(CogBase):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ) -> None:
        super().__init__(bot, sessionmaker)

        self.youtube: "YouTubeResource" = googleapiclient.discovery.build(
            "youtube", "v3", developerKey=os.getenv("GOOGLE_API_KEY", "dummy")
        )

    @tasks.loop(hours=1)
    async def check_subscription(self) -> None:
        """Check for upcoming live of WCAS.

        If found, post an announcement in the relevant channels."""

        if not os.getenv("GOOGLE_API_KEY"):
            logger.debug("GOOGLE_API_KEY not set, skipping WCAS check.")
            return

        WCAS_UPLOAD_ID = "UUF-gSgJSzQbWUBL-dLDDF9Q"
        HKITHUB_PODCAST_CHANNEL = 1398697140754190460

        try:
            playlist_items = (
                self.youtube.playlistItems()
                .list(
                    part="contentDetails",
                    maxResults=25,
                    playlistId=WCAS_UPLOAD_ID,
                )
                .execute()
            )

            # TODO: Get announcement history from database
            announcement_history = []

        except Exception as e:
            logger.error(e)

    @check_subscription.before_loop
    async def check_subscription_wait(self) -> None:
        await self.bot.wait_until_ready()

    @discord.app_commands.command()
    @discord.app_commands.checks.has_permissions(manage_channels=True)
    @discord.app_commands.guild_only()
    async def subscribe(self, ia: discord.Interaction) -> None:
        """(ADMIN) Subscribe (or unsubscribe) to a Youtube channel. Be notified of upcoming live streams.

        Note: Require bot channel to be set."""

        async with self.sessionmaker() as session:
            guild = (
                await session.execute(
                    select(Guild).where(Guild.guild_id == ia.guild.id)
                )
            ).scalar_one()

            if not guild.bot_channel:
                await ia.response.send_message("bot")

        await ia.response.send_message("resp")
