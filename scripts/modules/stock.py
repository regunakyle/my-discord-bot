from discord.ext import commands
from ..utility import Utility as Util


class Stock(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
