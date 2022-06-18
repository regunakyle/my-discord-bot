import discord, logging
from discord.ext import commands
from .utility import utility as util

# Modules
from .modules.steam import Steam
from .modules.meta import Meta
from .modules.general import General
from .modules.touhou import Touhou
from .modules.stock import Stock

logger = logging.getLogger(__name__)


class ErrorHandler(commands.Cog):
    """A cog for global error handling."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """A global error handler cog."""

        logger.error(error)

        if isinstance(error, commands.CommandNotFound):
            message = "This command does not exist."
        elif isinstance(error, commands.CommandOnCooldown):
            message = f"This command is on cooldown. Please try again after {round(error.retry_after, 1)} seconds."
        elif isinstance(error, commands.MissingPermissions):
            message = "You are missing the required permissions to run this command!"
        elif isinstance(error, commands.UserInputError):
            message = "Something about your input was wrong, please check your input and try again!"
        else:
            message = "Oh no! Something went wrong while running the command!"

        await ctx.send(message, reference=ctx.message)


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

    async def on_ready(self) -> None:
        logger.info("Logged in as " + self.user.name + " (" + str(self.user.id) + ").")
        self.add_cog(ErrorHandler(self))
        self.add_cog(Steam(self))
        self.add_cog(Meta(self))
        self.add_cog(General(self))
        self.add_cog(Touhou(self))
        self.add_cog(Stock(self))

    async def on_member_join(self, member: discord.member) -> None:
        channel = member.guild.system_channel
        if channel is not None:
            if member.guild.id == 651435165012459520:
                await channel.send(f"<@{member.id}>\nWelcome!")
            if member.guild.id == 200911777721090057:
                await channel.send(
                    f"<@{member.id}>\n歡迎加入本鄉!\n請先閱讀<#315162071945838592> <#680349727510102036> <#591934638964998144>並選取合適之身份組!"
                )

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return

        # Commands won't work without this line
        await self.process_commands(message)
