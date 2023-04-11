import logging
import os
import tempfile
import typing as ty

import aiohttp
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


class CogBase(commands.Cog):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ):
        self.bot = bot
        self.sessionmaker = sessionmaker

    def getMaxFileSize(self, nitroCount: int = 0) -> int:
        """Return the maximum file size (in MiB) supported by the current guild.

        If MAX_FILE_SIZE in .env is smaller than this size, return MAX_FILE_SIZE instead.
        """

        # Nitro level and their maximum upload size
        maxSize = 100
        if nitroCount < 7:
            maxSize = 25
        elif nitroCount < 14:
            maxSize = 50

        try:
            return min(maxSize, abs(int(os.getenv("MAX_FILE_SIZE"))))
        except:
            return maxSize

    async def download(self, url: str) -> ty.BinaryIO:
        """Download the content of <url> to <file> and return <file>.

        Note: NOT compatible with discord.File."""
        # TODO: Fix compatibility with discord.File
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
