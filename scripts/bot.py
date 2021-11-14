import discord
from discord.ext import commands
from .utility import utility as util

# Modules
from .modules.steam import Steam
from .modules.meta import Meta
from .modules.general import General
from .modules.touhou import Touhou


class ErrorHandler(commands.Cog):
    """A cog for global error handling."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """A global error handler cog."""

        if isinstance(error, commands.CommandNotFound):
            message = "This command does not exist."
        elif isinstance(error, commands.CommandOnCooldown):
            message = f"This command is on cooldown. Please try again after {round(error.retry_after, 1)} seconds."
        elif isinstance(error, commands.MissingPermissions):
            message = "You are missing the required permissions to run this command!"
        elif isinstance(error, commands.UserInputError):
            message = "Something about your input was wrong, please check your input and try again!"
        else:
            util.print(error)
            message = "Oh no! Something went wrong while running the command!"

        await ctx.send(message, reference=ctx.message)


class discordBot(commands.Bot):
    def __init__(
        self, command_prefix: str, intents: discord.Intents, activity: discord.Game
    ):
        super().__init__(
            command_prefix=command_prefix, intents=intents, activity=activity
        )

    intents = discord.Intents(messages=True, guilds=True)
    description = (
        "Discord bot for self use. \nWritten in Python, written by Reguna#9236."
    )
    activity = discord.Game(name=">>help")

    guildPref = util.runSQL("select * from guildInfo", None, True)

    async def on_ready(self) -> None:
        print("Logged in as " + self.user.name + " (" + str(self.user.id) + ").")
        self.add_cog(ErrorHandler(self))
        self.add_cog(Steam(self))
        self.add_cog(Meta(self))
        self.add_cog(General(self))
        self.add_cog(Touhou(self))

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return

        # Commands won't work without this line
        await self.process_commands(message)
