import logging
import re
import sys
import typing as ty
from pathlib import Path

import aiohttp
import discord
from discord.ext import commands
from gallery_dl import config, job
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.cogs._cog_base import CogBase, check_cooldown_factory

logger = logging.getLogger(__name__)


class General(CogBase):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ) -> None:
        super().__init__(bot, sessionmaker)

    @discord.app_commands.command()
    async def hello(
        self,
        ia: discord.Interaction,
    ) -> None:
        """Hello!"""

        await ia.response.send_message(
            file=discord.File(Path("./assets/images/hello.jpg"))
        )

    @discord.app_commands.command()
    @discord.app_commands.checks.dynamic_cooldown(check_cooldown_factory(2))
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(
        pixiv_link="Pixiv image link",
        image_number="Image number (for albums with multiple images); 1 by default",
        animation_format="Format for animations. GIF can loop, but might fail due to large size",
    )
    async def pixiv(
        self,
        ia: discord.Interaction,
        pixiv_link: str,
        image_number: int = 1,
        animation_format: ty.Literal["webm", "gif"] = "webm",
    ) -> None:
        """(RATE LIMITED) Upload an image from Pixiv. You may change the image number and/or animation format."""

        # TODO: Rewrite based on Phixiv
        # https://github.com/thelaao/phixiv

        match = re.compile(r"(www\.pixiv\.net\/(?:en\/)?artworks\/\d+)").search(
            pixiv_link
        )
        if not match:
            await ia.response.send_message("You link is invalid!")
            return

        # Delay response, maximum 15 mins
        await ia.response.defer()

        # Load Gallery-DL config and set maximum file size
        config.load(("./volume/gallery-dl/config.json",))
        config.set(
            ("downloader",),
            "filesize-max",
            f"{self.get_max_file_size(ia.guild)}M",
        )
        config.set(
            ("extractor",),
            "image-range",
            str(image_number),
        )
        config.set(
            ("extractor", "pixiv"),
            "image-range",
            str(image_number),
        )
        config.set(
            ("extractor",),
            "postprocessors",
            [
                {
                    "name": "ugoira",
                    "whitelist": ["pixiv"],
                    "extension": animation_format,
                    "ffmpeg-demuxer": "image2" if sys.platform == "linux" else "auto",
                }
            ],
        )

        download = job.DownloadJob(match.group(1))
        download.run()

        if download.status == 0:
            link = Path(download.pathfmt.path)

            if not link.is_file():
                await ia.followup.send(
                    f"Something went wrong.{' Maybe your image_number is out of range?' if image_number > 1 else ''}"
                )
                return

            embed = discord.Embed().add_field(
                name="Source", value=pixiv_link, inline=False
            )
            await ia.followup.send(
                embed=embed,
                file=discord.File(link),
            )
            link.unlink()

        else:
            match download.status:
                case 4:
                    # HttpError: Most probably because the image is too big
                    await ia.followup.send(
                        "Download failed. Most probably because your image is too big. (Maximum size: {size}MiB)".format(
                            size=self.get_max_file_size(ia.guild)
                        )
                    )
                    return
                case 8:
                    # NotFoundError: Invalid link
                    await ia.followup.send("You link is invalid!")
                    return
                case 16:
                    # AuthenticationError: No token provided
                    await ia.followup.send(
                        "Cannot login to Pixiv. Please notify the bot owner! \nBot owner: Please find instructions in https://github.com/regunakyle/my-discord-bot#pixiv-pixiv_link-image_number."
                    )
                    return
                case _:
                    logger.error(f"Gallery-DL failed. Status code: {download.status}")
                    await ia.followup.send(
                        "Something went wrong. Please notify the bot owner if this persists."
                    )
                    return

    @discord.app_commands.command()
    @discord.app_commands.checks.dynamic_cooldown(check_cooldown_factory(2))
    @discord.app_commands.guild_only()
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
        """(RATE LIMITED) Convert currency using data from Yahoo Finance."""
        # Delay response, maximum 15 mins
        await ia.response.defer()

        forex = (
            f"{starting_currency}{target_currency}=X"
            if starting_currency.lower() != "usd"
            else f"{target_currency}=X"
        )
        try:
            assert 0 < amount < 1e10

            amount = round(amount, 2)

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url=f"https://query2.finance.yahoo.com/v8/finance/chart/{forex}",
                    params={"range": "1d", "interval": "1d"},
                    timeout=10,
                ) as response:
                    quote = await response.json()
            # Funny response format
            newAmt = round(
                quote["chart"]["result"][0]["indicators"]["quote"][0]["close"][0]
                * amount,
                2,
            )
            await ia.followup.send(
                f"{amount} {starting_currency.upper()} = {newAmt} {target_currency.upper()}",
            )
        except AssertionError:
            await ia.followup.send(
                "Please enter a value between 0 and 1,000,000,000.",
            )
        except Exception as e:
            logger.error(e)
            await ia.followup.send(
                "Something went wrong. Most likely you inputted nonexistent currency code(s).",
            )
