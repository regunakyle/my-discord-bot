import datetime as dt
import logging
import re
import typing as ty
from time import mktime

import discord
import feedparser
from discord.ext import commands, tasks
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from .. import models
from .cog_base import CogBase

logger = logging.getLogger(__name__)


class Steam(CogBase):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ):
        super().__init__(bot, sessionmaker)
        self.taskName = "steam_giveaway"
        self.giveawayTask.start()

    @discord.app_commands.command()
    @discord.app_commands.checks.has_permissions(manage_channels=True)
    @discord.app_commands.guild_only()
    async def steam_subscribe(
        self,
        ia: discord.Interaction,
    ) -> None:
        """Subscribe to Steam giveaway notification, or unsubscribe if this server already subscribed."""
        resp = "Unsubscribed to steam giveaway notification."
        async with self.sessionmaker() as session:
            if (
                await session.execute(
                    delete(models.GuildTask)
                    .where(models.GuildTask.guild_id == ia.guild.id)
                    .where(models.GuildTask.task_name == self.taskName)
                )
            ).rowcount == 0:
                session.add(
                    models.GuildTask(guild_id=ia.guild.id, task_name=self.taskName)
                )
                resp = "Subscribed to steam giveaway notification."
            await session.commit()
        await ia.response.send_message(resp)

    @discord.app_commands.command()
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(
        target_domain="Domain of the game site you wish to blacklist. Unblacklist if it is in blacklist.",
    )
    async def blacklist(
        self,
        ia: discord.Interaction,
        target_domain: str = None,
    ) -> None:
        """Blacklist domains for the steam giveaway task. Show current blacklists if no domain inputted."""
        # Delay response, maximum 15 mins
        await ia.response.defer()

        async with self.sessionmaker() as session:
            if target_domain:
                resp = f"The domain ***{target_domain.lower()}*** is deleted from database."
                if (
                    await session.execute(
                        delete(models.SteamBlacklist)
                        .where(models.SteamBlacklist.guild_id == ia.guild.id)
                        .where(models.SteamBlacklist.keyword == target_domain)
                    )
                ).rowcount == 0:
                    session.add(
                        models.SteamBlacklist(
                            guild_id=ia.guild.id, keyword=target_domain.lower()
                        )
                    )
                    resp = f"Keyword ***{target_domain.lower()}*** added to database."
                await session.commit()
                await ia.followup.send(resp)
                return

            # Send the list of blacklisted domains back to user
            blacklists: ty.List[models.SteamBlacklist] = (
                await session.execute(
                    select(models.SteamBlacklist).where(
                        models.SteamBlacklist.guild_id == ia.guild.id
                    )
                )
            ).scalars()

        resp = f"Keyword blacklist for ***{ia.guild.name}***:\n"
        if blacklists:
            for index, blacklist in enumerate(blacklists, start=1):
                resp += f"{index}: ***{blacklist.keyword}***\n"
            resp = blacklist[:-1]
        else:
            resp += "Empty. Maybe you should add something here?"
        await ia.followup.send(resp)

    # Schedule Job Scripts Start
    async def checkGiveaway(self) -> None:
        logger.info("Fetching data from isthereanydeal.com...")
        datePattern = re.compile(r"[eE]xpires? on (\d{4}-\d{2}-\d{2})")
        rss = feedparser.parse(
            await self.download("https://isthereanydeal.com/rss/specials/us")
        )

        giveaway_records = []
        for entry in rss.entries:
            if "giveaway" in entry["title"] and "expired" not in entry["summary"]:
                # Time in UTC
                async with self.sessionmaker() as session:
                    try:
                        publish_time = dt.datetime.fromtimestamp(
                            mktime(entry["published_parsed"])
                        )
                        await session.execute(
                            insert(models.SteamGiveawayHistory).values(
                                title=entry["title"],
                                link=entry["link"],
                                publish_time=publish_time,
                                expiry_time=(
                                    dt.datetime.strptime(
                                        datePattern.search(entry["summary"]).group(1),
                                        r"%Y-%m-%d",
                                    )
                                    if datePattern.search(entry["summary"])
                                    else None
                                ),
                            )
                        )
                        await session.commit()
                    except Exception as e:
                        pass
        logger.info("Check giveaway ended.")

    async def getNewGiveaway(
        self, guildId: str
    ) -> ty.List[models.SteamGiveawayHistory]:
        # TODO: Use regex to filter Domain
        return []
        results = self.runSQL(
            """
        SELECT
            ltrim(sgh.Title,'[giveaway] ') 'Title',
            sgh.Link,
            sgh.PublishTime,
            sgh.ExpiryDate,
            substr(sgh.Link,instr(sgh.Link,'://')+ 3,instr(sgh.Link,'com/')-instr(sgh.Link,'://')) 'Domain'
        FROM
            SteamGiveawayHistory sgh
        INNER JOIN GuildInfo gi 
                ON
            gi.GuildId = ?
            AND sgh.PublishTime > gi.LastUpdated
        ORDER BY
            PublishTime DESC
        """,
            [guildId],
        )
        self.runSQL("UPDATE GuildInfo SET LastUpdated = Datetime()")
        blacklist = self.runSQL(
            "SELECT Keyword FROM SteamBlacklist WHERE guildId = ?", [guildId]
        )
        filteredResults = []
        if results:
            for result in results:
                inBlacklist = False
                if blacklist:
                    for item in blacklist:
                        if item["Keyword"] in result["Domain"]:
                            inBlacklist = True
                            break
                if inBlacklist == False:
                    filteredResults.append(result)
        else:
            filteredResults = None
        return filteredResults

    @tasks.loop(hours=12)
    async def giveawayTask(self) -> None:
        await self.checkGiveaway()
        async with self.sessionmaker() as session:
            guild_tasks: ty.List[models.GuildTask] = (
                await session.execute(
                    select(models.GuildTask)
                    .options(
                        selectinload(models.GuildTask.guild_info),
                    )
                    .where(models.GuildTask.task_name == self.taskName)
                )
            ).scalars()
        for guild_task in guild_tasks:
            newGiveaways = await self.getNewGiveaway(guild_task.guild_info.guild_id)

            if not (
                botChannel := self.bot.get_channel(guild_task.guild_info.bot_channel)
            ):
                logger.warning(
                    f"This guild (id: {guild_task.id}, name: {guild_task.guild_info.guild_name}) has not yet set a bot channel!"
                )
                continue

            for item in newGiveaways:
                icon = discord.File("./assets/images/steam.png", filename="steam.png")
                embed = (
                    discord.Embed(title=item["Title"], url=item["Link"])
                    .set_thumbnail(url="attachment://steam.png")
                    .add_field(
                        name="Publish date", value=item["PublishTime"], inline=False
                    )
                )
                if item["ExpiryDate"]:
                    embed.add_field(
                        name="Expiry date", value=item["ExpiryDate"], inline=False
                    )
                await botChannel.send(file=icon, embed=embed)
