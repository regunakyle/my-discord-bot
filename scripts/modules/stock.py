from discord.ext import commands
from ..utility import utility as util

# TODO: 4 task(s)
# Stock quote
# Daily P/L reminder
# Portfolio import


class Stock(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
