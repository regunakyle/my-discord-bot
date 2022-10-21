import discord, logging, typing as ty
from discord.ext import commands
from pathlib import Path
from .utility import Utility as Util

# Modules
from .modules.steam import Steam
from .modules.meta import Meta
from .modules.general import General
from .modules.finance import Finance
from .modules.music import Music

logger = logging.getLogger(__name__)


class ErrorHandler(commands.Cog):
    """A cog for global error handling."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.tree.on_error = self.on_app_command_error

    async def on_app_command_error(
        self, ia: discord.Interaction, e: discord.app_commands.AppCommandError
    ) -> None:
        logger.error(e)
        try:
            await ia.response.send_message(
                "Oh no! Something unexpected happened!",
                file=discord.File(Path("./assets/images/error.jpg")),
            )
        except discord.errors.InteractionResponded:
            await ia.followup.send(
                "Oh no! Something unexpected happened!",
                file=discord.File(Path("./assets/images/error.jpg")),
            )


class discordBot(commands.Bot):
    def __init__(
        self,
        command_prefix: str,
        intents: discord.Intents,
        activity: discord.Game,
        description: str,
    ):
        super().__init__(
            command_prefix=command_prefix,
            intents=intents,
            activity=activity,
            description=description,
        )
        # Disable prefixed help command, use /help instead
        self.help_command = None

    async def on_ready(self) -> None:
        logger.info(f"Logged in as {self.user.name} ({str(self.user.id)}).")
        await self.add_cog(ErrorHandler(self))
        await self.add_cog(Steam(self))
        await self.add_cog(Meta(self))
        await self.add_cog(General(self))
        await self.add_cog(Finance(self))
        await self.add_cog(Music(self))

    # TODO: Dynamic welcome message
    async def on_member_join(self, member: discord.member) -> None:
        channel = member.guild.system_channel
        if channel is not None:
            if member.guild.id in [651435165012459520, 1000302465276710943]:
                await channel.send(f"<@{member.id}>\nWelcome!")
            if member.guild.id == 200911777721090057:
                await channel.send(
                    f"<@{member.id}>\n歡迎加入本鄉!\n請先閱讀<#315162071945838592> <#680349727510102036> <#591934638964998144>並選取合適之身份組!"
                )
