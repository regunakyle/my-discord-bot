import csv
import io
import logging
import re
import time
import typing as ty

import discord
import feedparser
from discord.ext import commands, tasks
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session

from .cog_base import CogBase

logger = logging.getLogger(__name__)


class Steam(CogBase):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ):
        super().__init__(bot, sessionmaker)
        self.giveawayTask.start()

    @discord.app_commands.command()
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(
        target_domain="Domain of the game site you wish to blacklist",
        is_remove="Set to True if you want to remove <target_domain> from blacklist",
    )
    async def blacklist(
        self,
        ia: discord.Interaction,
        target_domain: str = None,
        is_remove: bool = False,
    ) -> None:
        """Blacklist domains for the find giveaway task."""
        # Delay response, maximum 15 mins
        await ia.response.defer()
        if target_domain:
            if is_remove:
                if self.runSQL(
                    "SELECT 1 FROM SteamBlacklist WHERE Keyword = ?",
                    [target_domain.lower()],
                ):
                    self.runSQL(
                        "DELETE FROM SteamBlacklist WHERE Keyword = ?",
                        [target_domain.lower()],
                    )
                    await ia.followup.send(
                        f"The keyword ***{target_domain.lower()}*** is deleted from database.",
                    )
                else:
                    await ia.followup.send(
                        f"Keyword ***{target_domain.lower()}*** not found.",
                    )
            else:
                try:
                    self.runSQL(
                        "INSERT INTO SteamBlacklist VALUES (?,?,datetime())",
                        [target_domain.lower(), ia.guild.id],
                    )
                    await ia.followup.send(
                        f"Keyword ***{target_domain.lower()}*** added to database."
                    )
                except ValueError as e:
                    logger.error(e)
                    await ia.followup.send(
                        "Insert keyword failed: Probably because this keyword already exists in the database.",
                    )
                    return
        result = self.runSQL(
            "SELECT rowid,* FROM SteamBlacklist WHERE GuildId = ?",
            [ia.guild.id],
        )

        blacklist = f"Keyword blacklist for ***{ia.guild.name}***:\n"
        if result:
            for item in result:
                blacklist += f'{str(item["rowid"])}:***{item["Keyword"]}***\n'
            blacklist = blacklist[:-1]
        else:
            blacklist += "Empty. Maybe you should add something here?"
        await ia.followup.send(blacklist)

    # Schedule Job Scripts Start
    def checkGiveaway(self) -> None:
        logger.info("Fetching data from isthereanydeal.com...")
        datePattern = re.compile(r"[eE]xpires? on (\d{4}-\d{2}-\d{2})")
        # TODO: Use an async library to get RSS file, then pass it to feedparser
        rss = feedparser.parse("https://isthereanydeal.com/rss/specials/us")
        for entry in rss.entries:
            if "giveaway" in entry["title"] and "expired" not in entry["summary"]:
                # Time in UTC
                publishTime = time.strftime(
                    r"%Y-%m-%d %H:%M:%S", entry["published_parsed"]
                )
                expiryDate = (
                    datePattern.search(entry["summary"]).group(1)
                    if datePattern.search(entry["summary"])
                    else None
                )
                try:
                    self.runSQL(
                        "INSERT INTO SteamGiveawayHistory VALUES (?,?,?,?)",
                        [entry["title"], entry["link"], publishTime, expiryDate],
                    )
                    logger.info(
                        f"""New record inserted into database. 
                        Title: {entry["title"]}
                        Publish Time: {publishTime}
                        """
                    )
                except:
                    # Skip if error occurs, e.g. record already exists
                    pass
        logger.info("Check giveaway ended.")

    def getNewGiveaway(self, guildId: str) -> tuple | None:
        channel = self.runSQL(
            "SELECT BotChannel FROM GuildInfo WHERE GuildId = ?", [guildId]
        )
        if channel is None or channel[0]["BotChannel"] is None:
            return None
        # TODO: Use regex to filter Domain
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
        return channel[0]["BotChannel"], filteredResults

    @tasks.loop(hours=12)
    async def giveawayTask(self) -> None:
        self.checkGiveaway()
        for guild in self.bot.guilds:
            newList = self.getNewGiveaway(guild.id)
            if newList == None:
                logger.warning(
                    f"This guild (id: {guild.id}, name: {guild.name}) has not yet set a bot channel!"
                )
                continue
            channel = self.bot.get_channel(int(newList[0]))
            if newList[1]:
                for item in newList[1]:
                    icon = discord.File(
                        "./assets/images/steam.png", filename="steam.png"
                    )
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
                    if channel:
                        await channel.send(file=icon, embed=embed)
