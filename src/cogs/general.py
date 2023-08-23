import asyncio
import logging
import re
import typing as ty
from pathlib import Path

import aiohttp
import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .cog_base import CogBase, check_cooldown

logger = logging.getLogger(__name__)


class General(CogBase):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ):
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
    @discord.app_commands.checks.dynamic_cooldown(check_cooldown)
    @discord.app_commands.guild_only()
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
        """(RATE LIMITED) Show the <image_number>th picture (or video) of [pixiv_link]."""

        match = re.compile(r"(www\.pixiv\.net\/(?:en\/)?artworks\/\d+)").search(
            pixiv_link
        )
        if not match:
            await ia.response.send_message("You link is invalid!")
            return

        link = match.group(1)

        # Delay response, maximum 15 mins
        await ia.response.defer()

        # Both Discord and Gallery-DL use MiB
        command = f"gallery-dl {link} --range {int(image_number)} --ugoira-conv --filesize-max {self.get_max_file_size(ia.guild.premium_subscription_count)}M"

        proc = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            if match := re.compile(
                r"File size larger than allowed maximum \((\d+) > (\d+)\)"
            ).search(stderr.decode()):
                toMebibyte = lambda x: f"{int(x) / 1024 / 1024 :.2f}"
                await ia.followup.send(
                    f"Your image is too big! (Maximum size allowed: {toMebibyte(match.group(2))} MiB, your image is {toMebibyte(match.group(1))} MiB)"
                )
            else:
                await ia.followup.send(f"Something went wrong: \n{stderr.decode()}")
        else:
            link = Path(
                f'./volume/gallery-dl/{re.compile(r"pixiv.*").search(stdout.decode()).group()}'
            )

            embed = (
                discord.Embed(title="Pixiv Image")
                .add_field(
                    name="Shared by",
                    value=f"{ia.user.display_name}",
                    inline=False,
                )
                .add_field(name="Source", value=pixiv_link, inline=False)
            )
            await ia.followup.send(
                embed=embed,
                file=discord.File(link),
            )
            link.unlink()

    @discord.app_commands.command()
    @discord.app_commands.checks.dynamic_cooldown(check_cooldown)
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
        except AssertionError as e:
            await ia.followup.send(
                "Please enter a value between 0 and 1,000,000,000.",
            )
        except Exception as e:
            logger.error(e)
            await ia.followup.send(
                "Something went wrong. Most likely you inputted nonexistent currency code(s).",
            )
