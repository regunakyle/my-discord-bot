import discord, typing as ty, logging, os, datetime as dt
from discord.ext import commands
from ..utility import Utility as Util

# TODO: 1 Task(s)
# Custom help command
logger = logging.getLogger(__name__)


class MyHelpCommand(commands.MinimalHelpCommand):
    # Reference: https://gist.github.com/InterStella0/b78488fb28cadf279dfd3164b9f0cf96
    def get_command_signature(self, command: commands) -> str:
        return "%s%s %s" % (
            self.clean_prefix,
            command.qualified_name,
            command.signature,
        )

    async def send_bot_help(self, mapping: dict) -> None:
        embed = discord.Embed(title="Help")
        for cog, commands in mapping.items():
            filtered = await self.filter_commands(commands, sort=True)
            command_signatures = [self.get_command_signature(c) for c in filtered]
            if command_signatures:
                cog_name = getattr(cog, "qualified_name", "No Category")
                embed.add_field(
                    name=cog_name, value="\n".join(command_signatures), inline=False
                )

        channel = self.get_destination()
        await channel.send(embed=embed)


class Meta(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = MyHelpCommand()
        bot.help_command.cog = self

    def cog_unload(self) -> None:
        self.bot.help_command = self._original_help_command

    @commands.command()
    async def setBotChannel(
        self, ctx: commands.Context, is_unset: ty.Optional[str] = None
    ) -> None:
        """Set the channel for bot notifications.
        Input anything after the command to unset bot channel from this guild."""
        try:
            if is_unset:
                Util.runSQL(
                    "UPDATE guildInfo SET BotChannel = null where GuildId = ?",
                    [ctx.guild.id],
                )
            else:
                Util.runSQL(
                    "INSERT OR REPLACE INTO guildInfo values (?,?,?,Datetime())",
                    [ctx.guild.id, ctx.guild.name, ctx.channel.id],
                )
            await ctx.channel.send("Update complete.", reference=ctx.message)
        except Exception as e:
            logger.error(e)
            await ctx.send(
                "Operation failed. Something went wrong.", reference=ctx.message
            )

    @commands.command()
    async def log(self, ctx: commands.Context, number_of_days: str = "0") -> None:
        """Send log file from ***number_of_days*** days ago (by default today).
        Only usable by privilaged users.
        """
        try:
            assert int(number_of_days) != 0
            dateString = dt.date.strftime(
                dt.date.today() + dt.timedelta(days=int(number_of_days)),
                format=r".%Y-%m-%d",
            )
        except Exception as e:
            dateString = ""

        if ctx.author.id == 263243377821089792:
            link = os.path.join(
                os.getcwd(), "volume", "logs", f"discord.log{dateString}"
            )
            if os.path.isfile(link):
                await ctx.send(file=discord.File(link), reference=ctx.message)
            else:
                await ctx.send(
                    f"File {'discord.log' + dateString} not found.",
                    reference=ctx.message,
                )
        else:
            await ctx.send(
                "Only privilaged user may use this command.", reference=ctx.message
            )
