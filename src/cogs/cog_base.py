import logging
import os
import tempfile
import typing as ty

import aiohttp
import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


# TODO: Find a way to put this function in CogBase while being
# compatible with the dynamic_cooldown decorator
def check_cooldown(
    ia: discord.Interaction,
) -> discord.app_commands.Cooldown | None:
    """Global cooldown for commands, maximum 1 use per 2.5 seconds (unlimited for the bot owner)"""
    if ia.user.id == ia.client.application.owner.id:
        return None
    return discord.app_commands.Cooldown(1, 2.5)


class CogBase(commands.Cog):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ):
        self.bot = bot
        self.sessionmaker = sessionmaker

    def get_max_file_size(self, nitroCount: int = 0) -> int:
        """Return the maximum file size (in MiB) supported by the current guild.

        If MAX_FILE_SIZE in .env is smaller than this size, return MAX_FILE_SIZE instead.
        """

        # Nitro level and their maximum upload size
        maxSize = 100  # Level 3
        if nitroCount < 7:  # Level 1 or lower
            maxSize = 25
        elif nitroCount < 14:  # Level 2
            maxSize = 50

        try:
            return min(maxSize, abs(int(os.getenv("MAX_FILE_SIZE"))))
        except:
            return maxSize

    async def download(self, url: str) -> ty.BinaryIO:
        """Download the content of <url> to <file> and return <file>.

        Note: NOT compatible with discord.File."""
        # TODO: Fix compatibility issue with discord.File
        file = tempfile.TemporaryFile()
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                while True:
                    chunk = await response.content.read(4096)
                    if not chunk:
                        break
                    file.write(chunk)
        file.seek(0)
        return file
