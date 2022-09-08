import discord, typing as ty, logging, os, datetime as dt
from discord.ext import commands
from discord import app_commands
from pathlib import Path
from ..utility import Utility as Util

# TODO: 1 Task(s)
# Slash help command
# Set new member welcome message (from db)
logger = logging.getLogger(__name__)


class Meta(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    # @commands.is_owner()
    async def sync(
        self,
        ctx: commands.Context,
        guilds: commands.Greedy[discord.Object],
        spec: ty.Optional[ty.Literal["~", "*", "^"]] = None,
    ) -> None:
        if not guilds:
            if spec == "~":
                # sync current guild, for guild specific commands
                synced = await self.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                # copies all global app commands to current guild and syncs
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                # clears all commands from the current guild target and syncs
                # (removes guild commands)
                self.bot.tree.clear_commands(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                # global sync
                synced = await self.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return

        # <prefix>sync id_1 id_2 -> syncs guilds with id 1 and 2
        ret = 0
        for guild in guilds:
            try:
                await self.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    @discord.app_commands.command()
    @discord.app_commands.describe(
        command_name="Set to True if you want to unsubscribe from all notifications",
    )
    async def help(self, ia: discord.Interaction, command_name: str = None) -> None:
        await ia.response.send_message(self.bot.description)

    @commands.command()
    async def test(self, ctx: commands.Context) -> None:
        """Reload application commands (i.e. slash commands)"""
        test = self.bot.tree.get_commands(guild=ctx.guild)
        embed = discord.Embed(
            title="IT Dog Bot: Help",
            description=f"{self.bot.description}<@Reguna>",
            color=discord.Colour.from_str("#00ff2f"),
        )
        embed.set_author(
            name="Reguna (@Reguna#9236)",
            url="https://github.com/regunakyle/MyDiscordBot",
            icon_url="https://pbs.twimg.com/media/Fb0DzG9WIAALL2U?format=jpg&name=small",
        )
        await ctx.send(embed=embed)

    @discord.app_commands.command()
    @discord.app_commands.describe(
        is_unset="Set to True if you want to unsubscribe from all notifications",
    )
    async def setbotchannel(
        self, ia: discord.Interaction, is_unset: bool = False
    ) -> None:
        """Set the channel for bot notifications.
        Input anything after the command to unset bot channel from this guild."""
        try:
            if is_unset:
                Util.runSQL(
                    """UPDATE GuildInfo SET BotChannel = null WHERE GuildId = ?""",
                    [ia.guild.id],
                )
            else:
                Util.runSQL(
                    "INSERT OR REPLACE INTO GuildInfo VALUES (?,?,?,Datetime())",
                    [ia.guild.id, ia.guild.name, ia.channel.id],
                )
            await ia.response.send_message("Update complete.")
        except Exception as e:
            logger.error(e)
            await ia.response.send_message("Operation failed. Something went wrong.")

    @discord.app_commands.command()
    @discord.app_commands.describe(
        number_of_days="Number of days from today",
    )
    async def log(self, ia: discord.Interaction, number_of_days: int = 0) -> None:
        """Get logs. Only the owner of the bot can use this."""
        if not await self.bot.is_owner(ia.user):
            await ia.response.send_message("Only the bot owner may use this command!")
            return

        try:
            assert int(number_of_days) != 0
            dateString = dt.date.strftime(
                dt.date.today() + dt.timedelta(days=int(number_of_days)),
                format=r".%Y-%m-%d",
            )
        except Exception:
            dateString = ""

        fileName = f"discord.log{dateString}"
        link = Path(f"./volume/logs/{fileName}")
        if link.is_file():
            await ia.response.send_message(file=discord.File(link))
        else:
            await ia.response.send_message(
                f"File {fileName} not found.",
            )
