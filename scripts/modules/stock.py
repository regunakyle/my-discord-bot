import yfinance as yf
from discord.ext import commands

# TODO: 5 Task(s)
# Function: Routine: Get latest quote, stating price change & gain/loss
# Function: Buy/sell recording to database
# Function: Show inventory
# Function: Show buy/sell record
# Move currency conversion function to here


class Stock(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
