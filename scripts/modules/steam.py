import feedparser
from ..utility import utility as util
import datetime
import re
import csv
import discord
from discord.ext import commands, tasks


class Steam(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.giveawayTask.start()

    def checkGiveaway(self) -> None:
        print("Fetching data from isthereanydeal.com...")
        datePattern = re.compile("[eE]xpires? on (\d{4}-\d{2}-\d{2})")
        rss = feedparser.parse("https://isthereanydeal.com/rss/specials/us")
        for entry in rss.entries:
            if "giveaway" in entry["title"] and "expired" not in entry["summary"]:
                # Time in UTC +0
                publishTime = util.strftime(
                    datetime.datetime(*entry["published_parsed"][:6])
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
                    util.print(
                        "New record inserted into database. \nTitle: "
                        + entry["title"]
                        + "\nPublish Time: "
                        + publishTime
                        + "\n"
                    )
                except:
                    # print('Record already found in database. \nTitle: '+entry['title']+'\nPublish Time: '+publishTime+'\n')
                    pass
        print("Check giveaway ended.")

    def getNewGiveaway(self, guildId: str) -> tuple:
        channel = util.runSQL(
            "select BotChannel from guildInfo where GuildId = ?", [guildId], True
        )[0]["BotChannel"]
        if channel is None:
            return (None, None)
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
            True,
        )
        util.runSQL(
            """
        UPDATE guildInfo
        SET LastUpdated = Datetime()
        """
        )
        filter = util.runSQL(
            "select Keyword from steam_Blacklist where guildId = ?", [guildId], True
        )
        filteredResults = []
        if results:
            for result in results:
                dummy = False
                for item in filter:
                    if item["Keyword"] in result["Domain"]:
                        dummy = True
                        break
                if dummy == False:
                    filteredResults.append(result)
        else:
            filteredResults = None
        return channel, filteredResults

    @commands.command()
    async def getAllRecord(self, ctx: commands.Context) -> None:
        """List all record in database"""
        location = "./volume/assets/temp/GiveawayList.csv"
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
                True,
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
        self, ctx: commands.Context, domain: str = None, job: str = None
    ) -> None:
        if job and domain and job.lower() == "-r":
            util.runSQL(
                "delete from steam_Blacklist where Keyword = ?", [domain.lower()]
            )
            await ctx.send(
                "If ***" + domain.lower() + "*** is in database, it should be deleted.",
                reference=ctx.message,
            )
            await self.blacklist(ctx)
        else:
            if domain is None:
                blacklist = "Keyword blacklist for ***" + ctx.guild.name + "***:\n"
                for item in util.runSQL(
                    "SELECT rowid,* FROM steam_Blacklist where GuildId = ?",
                    [ctx.guild.id],
                    True,
                ):
                    blacklist += str(item["rowid"]) + ":***" + item["Keyword"] + "***\n"
                blacklist = blacklist[:-1]
                await ctx.send(blacklist, reference=ctx.message)
            else:
                try:
                    util.runSQL(
                        "insert into steam_Blacklist values (?,?,datetime())",
                        [domain.lower(), ctx.guild.id],
                    )
                    await ctx.send(
                        "Keyword ***" + domain.lower() + "*** added to database.",
                        reference=ctx.message,
                    )
                except ValueError as e:
                    await ctx.send(
                        "Insert keyword failed: Probably because this keyword already exists in the database.",
                        reference=ctx.message,
                    )

    @tasks.loop(hours=2)
    async def giveawayTask(self) -> None:
        self.checkGiveaway()
        for guild in self.bot.guilds:
            newlist = self.getNewGiveaway(guild.id)
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
