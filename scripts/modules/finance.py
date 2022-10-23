from discord.ext import commands
from ..utility import Utility as Util
import discord, typing as ty, yfinance as yf, logging

logger = logging.getLogger(__name__)


class Finance(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command()
    @discord.app_commands.describe(
        amount="Amount in <starting_currency>, ranged from 0 to 1,000,000,000",
        starting_currency="Starting currency, e.g. HKD",
        target_currency="Target currency, e.g. USD",
    )
    async def forex(
        self,
        ia: discord.Interaction,
        amount: float,
        starting_currency: str,
        target_currency: str,
    ) -> None:
        """Convert currency using data from Yahoo Finance."""
        # TODO: Use an async library

        # Delay response, maximum 15 mins
        await ia.response.defer()

        forex = (
            f"{starting_currency}{target_currency}=X"
            if starting_currency.lower() != "usd"
            else f"{target_currency}=X"
        )
        try:
            assert 0 <= float(amount) < 1e10
            newAmt = round(
                yf.Ticker(forex).history("1d").iloc[0]["Close"] * float(amount), 2
            )
            await ia.followup.send(
                f"{amount} {starting_currency} = {str(newAmt)} {target_currency}",
            )
        except AssertionError as e:
            await ia.followup.send(
                "Please enter a value between 0 and 1,000,000,000.",
            )
        except Exception as e:
            logger.error(e)
            await ia.followup.send(
                "Something went wrong. Most likely you inputted nonexistent currency code(s).",
            )
