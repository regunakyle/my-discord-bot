import asyncio
import logging
import re
import typing as ty
from pathlib import Path

import discord
from discord.ext import commands

from ..utility import Utility as Util

logger = logging.getLogger(__name__)


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
        command = f"gallery-dl {link} --range {image_number} --ugoira-conv --filesize-max {Util.getMaxFileSize(ia.guild.premium_subscription_count)}M"

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
