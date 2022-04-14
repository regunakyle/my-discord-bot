import discord, typing as ty
from discord.ext import commands
from ..utility import utility as util

# TODO: 1 Task(s)
# Custom help command
# Show log


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
        self, ctx: commands.Context, unset: ty.Optional[str] = None
    ) -> None:
        """Set the channel for bot notifications."""
        try:
            util.runSQL(
                "INSERT OR REPLACE INTO guildInfo values (?,?,?,Datetime())",
                [
                    ctx.guild.id,
                    ctx.guild.name,
                    ctx.channel.id if unset is None else None,
                ],
            )
            await ctx.channel.send("Update complete.", reference=ctx.message)
        except Exception as e:
            util.print(e)
            await ctx.send(
                "Operation failed. Something went wrong.", reference=ctx.message
            )

    @commands.command()
    async def log(self, ctx: commands.Context, date: str = None) -> None:
        """Send log file for a specific date (by default latest date)."""
        print("hi")
