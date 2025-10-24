import datetime as dt
import logging
import os
import typing as ty

import discord
import googleapiclient.discovery
from discord.ext import commands, tasks
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import joinedload

from ..models import Guild
from ..models import Subscription as Sub
from ._cog_base import CogBase

if ty.TYPE_CHECKING:
    from googleapiclient._apis.youtube.v3 import YouTubeResource

logger = logging.getLogger(__name__)


class Subscription(CogBase):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ) -> None:
        super().__init__(bot, sessionmaker)

        # TODO: Handle connection failures
        self.youtube: "YouTubeResource" = googleapiclient.discovery.build(
            "youtube", "v3", developerKey=os.getenv("GOOGLE_API_KEY", "dummy")
        )
        self.check_subscription.start()

    @tasks.loop(hours=1)
    async def check_subscription(self) -> None:
        """Check for upcoming live of subscriptions.

        If found, post an announcement in the designated bot channel."""

        if not os.getenv("GOOGLE_API_KEY"):
            logger.debug("GOOGLE_API_KEY not set, skipping subscription check.")
            return

        logger.info("Checking for new live streams...")

        ISO_FORMAT = r"%Y-%m-%dT%H:%M:%SZ"
        MESSAGE_TEMPLATE = """{role_tag}
# {title}
{description}

**Link:**
https://www.youtube.com/watch?v={video_id}"""

        async with self.sessionmaker() as session:
            subscriptions = (
                (await session.execute(select(Sub).options(joinedload(Sub.guild))))
                .unique()
                .scalars()
            )

            for subscription in subscriptions:
                video_ids: ty.List[str] = []

                if not (
                    subscription.guild.bot_channel is not None
                    and (
                        bot_channel := self.bot.get_channel(
                            subscription.guild.bot_channel
                        )
                    )
                ):
                    logger.debug(
                        f"Bot channel not set for guild {subscription.guild.guild_name}"
                    )
                    continue

                try:
                    playlist_items = (
                        self.youtube.playlistItems()
                        .list(
                            part="contentDetails",
                            maxResults=50,
                            playlistId=subscription.youtube_upload_playlist,
                        )
                        .execute()
                    )

                    if "items" not in playlist_items:
                        logger.info(
                            f"No video found for channel id {subscription.youtube_channel_id}"
                        )
                        break

                    for item in playlist_items["items"]:
                        if (
                            "contentDetails" in item
                            and "videoPublishedAt" in item["contentDetails"]
                            and "videoId" in item["contentDetails"]
                        ):
                            # Assume that the playlist is sorted by publish date in descending order
                            if (
                                dt.datetime.strptime(
                                    item["contentDetails"]["videoPublishedAt"],
                                    ISO_FORMAT,
                                )
                                > subscription.last_checked_at
                            ):
                                video_ids.append(item["contentDetails"]["videoId"])
                            else:
                                break

                    subscription.last_checked_at = dt.datetime.now(dt.UTC)
                    await session.commit()

                    # Is there a limit to the number of IDs provided?
                    # TODO: Handle pageToken
                    videos = (
                        self.youtube.videos()
                        .list(
                            part="liveStreamingDetails,snippet",
                            id=",".join(video_ids),
                        )
                        .execute()
                    )

                    if "items" in videos:
                        for video in reversed(videos["items"]):
                            if "liveStreamingDetails" not in video:
                                # Not a live stream
                                continue

                            if (
                                "scheduledStartTime"
                                not in video["liveStreamingDetails"]
                                or "actualStartTime" in video["liveStreamingDetails"]
                            ):
                                # Not a scheduled stream or stream has already started
                                continue

                            logger.debug(
                                f"Sending notification of video title: `{video['snippet']['title']}` to {bot_channel.id}"
                            )
                            await bot_channel.send(
                                MESSAGE_TEMPLATE.format(
                                    role_tag=f"<@&{subscription.announcement_target}>"
                                    if subscription.announcement_target
                                    else "@everyone",
                                    title=video["snippet"]["title"],
                                    description=video["snippet"]["description"],
                                    video_id=video["id"],
                                )
                            )

                except Exception as e:
                    logger.error(e)

    @check_subscription.before_loop
    async def check_subscription_wait(self) -> None:
        await self.bot.wait_until_ready()

    @discord.app_commands.command()
    @discord.app_commands.checks.has_permissions(manage_channels=True)
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(
        channel_id="ID of the youtube channel you want to subscribe to",
        target_role_id="Discord role ID that you want to notify; @everyone if not provided",
    )
    async def subscribe(
        self,
        ia: discord.Interaction,
        channel_id: str,
        target_role_id: None | str = None,
    ) -> None:
        """(ADMIN) Subscribe (or unsubscribe) to a Youtube channel. Be notified of upcoming live streams.

        Note: Require bot channel to be set."""

        if target_role_id:
            try:
                int(target_role_id)
            except Exception:
                await ia.response.send_message("Invalid role id.")
                return

        await ia.response.defer()

        async with self.sessionmaker() as session:
            guild = (
                (
                    await session.execute(
                        select(Guild)
                        .where(Guild.guild_id == ia.guild.id)
                        .options(
                            joinedload(
                                Guild.subscriptions.and_(
                                    Sub.youtube_channel_id == channel_id
                                )
                            )
                        )
                    )
                )
                .unique()
                .scalar_one()
            )

            if not guild.bot_channel:
                await ia.followup.send("Bot channel not set. Use `/set_bot_channel`.")
                return

            if guild.subscriptions:
                await session.execute(
                    delete(Sub).where(Sub.youtube_channel_id == channel_id)
                )
                await session.commit()
                await ia.followup.send(
                    f"Unsubscribed from `{guild.subscriptions[0].youtube_channel_name}."
                )
                return

            channel = (
                self.youtube.channels()
                .list(part="contentDetails,snippet", id=channel_id)
                .execute()
            )

            if "items" not in channel:
                await ia.followup.send("Invalid YouTube channel ID")
                return

            if (
                "contentDetails" not in channel["items"][0]
                or "snippet" not in channel["items"][0]
            ):
                await ia.followup.send(
                    "Failed: Cannot find enough information for this Youtube channel."
                )
                return

            session.add(
                Sub(
                    guild_id=guild.id,
                    youtube_channel_id=channel_id,
                    youtube_channel_name=channel["items"][0]["snippet"]["title"],
                    youtube_upload_playlist=channel["items"][0]["contentDetails"][
                        "relatedPlaylists"
                    ]["uploads"],
                    announcement_target=target_role_id,
                )
            )

            await session.commit()

        await ia.followup.send(
            f"Successfully subscribed to `{channel['items'][0]['snippet']['title']}`."
        )
