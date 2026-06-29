import datetime as dt
import logging
import os
import typing as ty
import zoneinfo

import discord
import googleapiclient.discovery
from discord.ext import commands, tasks
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import joinedload

from ..exceptions import GuildNotFoundError
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

    @tasks.loop(minutes=15)
    async def check_subscription(self) -> None:
        """Check for upcoming live of subscriptions.

        If found, post an announcement in the designated bot channel."""

        if not os.getenv("GOOGLE_API_KEY"):
            logger.debug("GOOGLE_API_KEY not set, skipping subscription check.")
            return

        logger.debug("Checking for new live streams...")

        ISO_FORMAT = r"%Y-%m-%dT%H:%M:%SZ"
        MESSAGE_TEMPLATE = """{role_tag}
# {title}
## Scheduled Start Time
<t:{unix_timestamp}:F>
## Description
{description}
## Link
https://www.youtube.com/watch?v={video_id}"""

        async with self.sessionmaker() as session:
            subscriptions = (
                (await session.execute(select(Sub).options(joinedload(Sub.guild))))
                .unique()
                .scalars()
            )

            for subscription in subscriptions:
                video_ids: ty.List[str] = []

                notification_channel = self.bot.get_channel(
                    subscription.notification_channel_id
                )
                if notification_channel is None or not isinstance(
                    notification_channel, discord.abc.Messageable
                ):
                    logger.debug(
                        "Notification channel %d not found for subscription %s",
                        subscription.notification_channel_id,
                        subscription.youtube_channel_id,
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
                        continue

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

                            logger.info(
                                "Sending notification of video title: `%s` to %d",
                                video["snippet"]["title"],
                                notification_channel.id,
                            )
                            await notification_channel.send(
                                MESSAGE_TEMPLATE.format(
                                    role_tag=f"<@&{subscription.announcement_target}>"
                                    if subscription.announcement_target
                                    else "@everyone",
                                    title=video["snippet"]["title"],
                                    # HKT+8
                                    unix_timestamp=int(
                                        dt.datetime.fromisoformat(
                                            video["liveStreamingDetails"][
                                                "scheduledStartTime"
                                            ].replace("Z", "+00:00")
                                        ).timestamp()
                                    ),
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
        notification_channel="Channel where subscription notifications will be posted",
        target_role_id="Discord role ID that you want to notify; @everyone if not provided",
    )
    async def subscribe(
        self,
        ia: discord.Interaction,
        channel_id: str,
        notification_channel: discord.app_commands.AppCommandChannel,
        target_role_id: None | str = None,
    ) -> None:
        """(ADMIN) Subscribe to a Youtube channel. Be notified of upcoming live streams."""

        if target_role_id:
            try:
                int(target_role_id)
            except Exception:
                await ia.response.send_message("Invalid role id.")
                return

        # Validate notification channel permissions
        try:
            guild_channel = await notification_channel.fetch()
        except discord.Forbidden:
            await ia.response.send_message(
                "ERROR: The bot does not have permission to view that channel.",
                ephemeral=True,
            )
            return

        if not guild_channel.permissions_for(ia.guild.me).send_messages:
            await ia.response.send_message(
                "ERROR: The bot needs to have write access to that channel.",
                ephemeral=True,
            )
            return

        await ia.response.defer()

        async with self.sessionmaker() as session:
            guild = (
                (
                    await session.execute(
                        select(Guild)
                        .where(Guild.guild_id == ia.guild.id)
                        .options(joinedload(Guild.subscriptions))
                    )
                )
                .unique()
                .scalar_one_or_none()
            )

            if guild is None:
                raise GuildNotFoundError(ia.guild)

            # Check if already subscribed
            for sub in guild.subscriptions:
                if sub.youtube_channel_id == channel_id:
                    await ia.followup.send(
                        f"Already subscribed to `{sub.youtube_channel_name}`.",
                    )
                    return

            channel = (
                self.youtube.channels()
                .list(part="contentDetails,snippet", id=channel_id)
                .execute()
            )

            if "items" not in channel:
                await ia.followup.send(
                    "ERROR: Invalid YouTube channel ID",
                    ephemeral=True,
                )
                return

            if (
                "contentDetails" not in channel["items"][0]
                or "snippet" not in channel["items"][0]
            ):
                await ia.followup.send(
                    "ERROR: Cannot find enough information for this Youtube channel.",
                    ephemeral=True,
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
                    notification_channel_id=notification_channel.id,
                )
            )

            await session.commit()

        await ia.followup.send(
            f"Successfully subscribed to `{channel['items'][0]['snippet']['title']}`."
        )

    @discord.app_commands.command()
    @discord.app_commands.checks.has_permissions(manage_channels=True)
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(
        channel_id="ID of the youtube channel you want to unsubscribe from",
    )
    async def unsubscribe(
        self,
        ia: discord.Interaction,
        channel_id: str,
    ) -> None:
        """(ADMIN) Unsubscribe from a Youtube channel."""
        # TODO: Create a interactive interface for user to choose what channel to unsubscribe from

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
                .scalar_one_or_none()
            )

            if guild is None:
                raise GuildNotFoundError(ia.guild)

            if not guild.subscriptions:
                await ia.followup.send(
                    f"Not subscribed to channel `{channel_id}`.",
                )
                return

            await session.execute(
                delete(Sub).where(Sub.youtube_channel_id == channel_id)
            )
            await session.commit()
            await ia.followup.send(
                f"Unsubscribed from `{guild.subscriptions[0].youtube_channel_name}`."
            )

    @discord.app_commands.command()
    @discord.app_commands.guild_only()
    async def subscription_status(self, ia: discord.Interaction) -> None:
        """Show the current subscription status of this guild."""
        await ia.response.defer(ephemeral=True)

        async with self.sessionmaker() as session:
            guild = (
                (
                    await session.execute(
                        select(Guild)
                        .where(Guild.guild_id == ia.guild.id)
                        .options(joinedload(Guild.subscriptions))
                    )
                )
                .unique()
                .scalar_one_or_none()
            )

            if guild is None:
                raise GuildNotFoundError(ia.guild)

            if not guild.subscriptions:
                await ia.followup.send("No subscriptions in this guild.")
                return

            embed = discord.Embed(
                title=f"Subscriptions ({len(guild.subscriptions)})",
                color=discord.Color.green(),
            )

            for sub in guild.subscriptions:
                notification_channel = self.bot.get_channel(sub.notification_channel_id)
                channel_mention = (
                    notification_channel.mention
                    if isinstance(notification_channel, discord.abc.Messageable)
                    else f"<#{sub.notification_channel_id}>"
                )
                target = (
                    f"<@&{sub.announcement_target}>"
                    if sub.announcement_target
                    else "@everyone"
                )

                embed.add_field(
                    name=sub.youtube_channel_name,
                    value=f"Channel ID: `{sub.youtube_channel_id}`\n"
                    f"Notifications: {channel_mention}\n"
                    f"Ping: {target}",
                    inline=False,
                )

            await ia.followup.send(embed=embed)
