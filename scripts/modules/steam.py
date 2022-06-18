import feedparser, datetime as dt, re, csv, discord, typing as ty, logging
from discord.ext import commands, tasks
from ..utility import utility as util

logger = logging.getLogger(__name__)


class Steam(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.giveawayTask.start()

    async def checkGiveaway(self) -> None:
        logger.info("Fetching data from isthereanydeal.com...")
        datePattern = re.compile(r"[eE]xpires? on (\d{4}-\d{2}-\d{2})")
        rss = feedparser.parse("https://isthereanydeal.com/rss/specials/us")
        for entry in rss.entries:
            if "giveaway" in entry["title"] and "expired" not in entry["summary"]:
                # Time in UTC +0
                publishTime = dt.datetime.strftime(
                    (dt.datetime(*entry["published_parsed"][:6])), r"%Y-%m-%d"
                )
                expiryDate = (
                    datePattern.search(entry["summary"]).group(1)
                    if datePattern.search(entry["summary"])
                    else None
                )
                try:
                    util.runSQL(
                        "Insert into steam_GiveawayHistory values (?,?,?,?)",
                        [entry["title"], entry["link"], publishTime, expiryDate],
                    )
                    logger.info(
                        "New record inserted into database. \nTitle: "
                        + entry["title"]
                        + "\nPublish Time: "
                        + publishTime
                        + "\n"
                    )
                except:
                    pass
        logger.info("Check giveaway ended.")

    def getNewGiveaway(self, guildId: str) -> ty.Union[tuple, None]:
        channel = util.runSQL(
            "select BotChannel from guildInfo where GuildId = ?", [guildId]
        )
        if channel is None or channel[0]["BotChannel"] is None:
            return None
        # TODO: Use regex to filter
        results = util.runSQL(
            """
        SELECT ltrim(sgh.Title,'[giveaway] ') 'Title', sgh.Link, sgh.PublishTime, sgh.ExpiryDate, substr(sgh.Link,instr(sgh.Link,'://')+3,instr(sgh.Link,'com/')-instr(sgh.Link,'://')) 'Domain'
        FROM steam_GiveawayHistory sgh 
		INNER JOIN guildInfo gi 
        ON gi.GuildId = ? AND sgh.PublishTime > gi.LastUpdated
        ORDER BY PublishTime DESC
        """,
            [guildId],
        )
        util.runSQL(
            """
        UPDATE guildInfo
        SET LastUpdated = Datetime()
        """
        )
        blacklist = util.runSQL(
            "select Keyword from steam_Blacklist where guildId = ?", [guildId]
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

    @commands.command()
    async def getAllRecord(self, ctx: commands.Context) -> None:
        """List all giveaway record in database"""
        location = "./assets/temp/GiveawayList.csv"
        with open(location, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Title", "Link", "Publish Time", "Expiry Date"])
            # TODO: Give only non-blacklisted items
            for item in util.runSQL(
                """select ltrim(Title,'[giveaway] ') 'Title',link,PublishTime,
                                        case when ExpiryDate is not NULL then ExpiryDate ELSE 'Unknown' END 'ExpiryDate'
                                        from steam_GiveawayHistory
                                        order by PublishTime desc""",
                None,
            ):
                writer.writerow(
                    [
                        item["Title"],
                        item["Link"],
                        item["PublishTime"],
                        item["ExpiryDate"],
                    ]
                )
        await ctx.send(file=discord.File(location), reference=ctx.message)

    @commands.command()
    async def blacklist(
        self, ctx: commands.Context, target_domain: str = None, is_remove: str = None
    ) -> None:
        """Blacklisting domains for the find giveaway task.
        >>blacklist : Display current blacklist for this guild
        >>blacklist <domain>: Add <domain> to blacklist; Add anything after <domain> to remove it from blacklist instead"""
        if is_remove and target_domain:
            util.runSQL(
                "delete from steam_Blacklist where Keyword = ?", [target_domain.lower()]
            )
            await ctx.send(
                "If ***"
                + target_domain.lower()
                + "*** is in database, it should be deleted.",
                reference=ctx.message,
            )
            await self.blacklist(ctx)
        else:
            if target_domain is None:
                result = util.runSQL(
                    "SELECT rowid,* FROM steam_Blacklist where GuildId = ?",
                    [ctx.guild.id],
                )
                blacklist = "Keyword blacklist for ***" + ctx.guild.name + "***:\n"
                if result:
                    for item in result:
                        blacklist += (
                            str(item["rowid"]) + ":***" + item["Keyword"] + "***\n"
                        )
                    blacklist = blacklist[:-1]
                await ctx.send(blacklist, reference=ctx.message)
            else:
                try:
                    util.runSQL(
                        "insert into steam_Blacklist values (?,?,datetime())",
                        [target_domain.lower(), ctx.guild.id],
                    )
                    await ctx.send(
                        "Keyword ***"
                        + target_domain.lower()
                        + "*** added to database.",
                        reference=ctx.message,
                    )
                except ValueError as e:
                    logger.error(e)
                    await ctx.send(
                        "Insert keyword failed: Probably because this keyword already exists in the database.",
                        reference=ctx.message,
                    )

    @tasks.loop(hours=2)
    async def giveawayTask(self) -> None:
        await self.checkGiveaway()
        for guild in self.bot.guilds:
            newlist = self.getNewGiveaway(guild.id)
            if newlist == None:
                logger.warning(
                    f"This guild (id: {guild.id}, name: {guild.name}) has not yet set a bot channel!"
                )
                continue
            channel = self.bot.get_channel(int(newlist[0]))
            if newlist[1]:
                for item in newlist[1]:
                    icon = discord.File(
                        "./assets/images/steam.png", filename="steam.png"
                    )
                    embed = discord.Embed(title=item["Title"], url=item["Link"])
                    embed.set_thumbnail(url="attachment://steam.png")
                    embed.add_field(
                        name="Publish date", value=item["PublishTime"], inline=False
                    )
                    if item["ExpiryDate"]:
                        embed.add_field(
                            name="Expiry date", value=item["ExpiryDate"], inline=False
                        )
                    if channel:
                        await channel.send(file=icon, embed=embed)
