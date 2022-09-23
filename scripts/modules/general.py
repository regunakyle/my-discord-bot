from discord.ext import commands
from pathlib import Path
from ..utility import Utility as Util
import subprocess, re, discord, os, typing as ty, yfinance as yf, logging

logger = logging.getLogger(__name__)


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command()
    async def hello(
        self,
        ia: discord.Interaction,
    ) -> None:
        """Because why not?"""

        await ia.response.send_message(
            file=discord.File(Path("./assets/images/hello.jpg"))
        )

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

    @discord.app_commands.command()
    @discord.app_commands.describe(
        pixiv_link="Pixiv image link",
        image_number="Image number (for albums with multiple images); 1 by default",
    )
    async def pixiv(
        self,
        ia: discord.Interaction,
        pixiv_link: str,
        image_number: int = 1,
    ) -> None:
        """Show the <image_number>th picture (or video) of [pixiv_link]."""
        link = (
            re.compile(r"(www\.pixiv\.net\/(?:en\/)?artworks\/[0-9]+)")
            .search(pixiv_link)
            .group()
        )

        # Delay response, maximum 15 mins
        await ia.response.defer()

        command = ["gallery-dl", link, "--range", str(image_number), "--ugoira-conv"]
        result = subprocess.run(command, capture_output=True, text=True)
        if len(result.stdout) == 0:
            await ia.followup.send(
                f"Something went wrong: \n{result.stderr if result.stderr else 'Image not found.'}"
            )
        else:
            link = Path(
                f'./volume/gallery-dl/{re.compile(r"pixiv.*").search(result.stdout).group()}'
            )

            sizeInBytes = round(link.stat().st_size / 1000 / 1000, 2)

            if (
                ia.guild.premium_subscription_count < 7 and sizeInBytes >= 8
            ):  # Server level 1 or below, file size 8MB maximum
                await ia.followup.send(
                    f"The image/video is too big! (8MB maximum supported, your image is {sizeInBytes}MB)"
                )
            elif (
                ia.guild.premium_subscription_count < 14 and sizeInBytes >= 16
            ):  # Server level 2, file size 50MB maximum
                await ia.followup.send(
                    f"The image/video is too big! (16MB maximum supported, your image is {sizeInBytes}MB)",
                )
            else:
                embed = (
                    discord.Embed(title="Pixiv Image")
                    .add_field(
                        name="Shared by",
                        value=f"{ia.user.display_name}#{ia.user.discriminator}",
                        inline=False,
                    )
                    .add_field(name="Source", value=pixiv_link, inline=False)
                )
                await ia.followup.send(
                    embed=embed,
                    file=discord.File(link),
                )
            link.unlink()
