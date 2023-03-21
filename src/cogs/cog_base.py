import logging
import os
import sqlite3
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
            maxSize = 8
        elif nitroCount < 14:
            maxSize = 16

        try:
            return min(maxSize, abs(int(os.getenv("MAX_FILE_SIZE"))))
        except:
            return maxSize

    def connectDB(self) -> ty.Tuple[sqlite3.Connection, sqlite3.Cursor]:
        """Connect to SQLite3 database, returning the connection and cursor (as a tuple)."""
        cnxn = sqlite3.connect("./volume/db.sqlite3")

        def dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict:
            d = {}
            for idx, col in enumerate(cursor.description):
                d[col[0]] = row[idx]
            return d

        cnxn.row_factory = dict_factory
        cursor = cnxn.cursor()
        return cnxn, cursor

    def runSQL(
        self, query: str, param: ty.List[ty.Any] | None = None
    ) -> ty.List[ty.Dict[str, ty.Any]] | None:
        """Run a SQL query and return the result as list of rows(as dict),

        or return None if no rows are returned.

        You should only run one SQL statement with each call to this function.
        """
        cnxn, cursor = self.connectDB()

        try:
            if param is None:
                cursor.execute(query)
            else:
                cursor.execute(query, param)

            SQLresult = cursor.fetchall()
            cnxn.commit()
            cursor.close()
            cnxn.close()
            return SQLresult if len(SQLresult) > 0 else None

        except Exception as e:
            cnxn.rollback()
            cursor.close()
            cnxn.close()
            raise ValueError(e)

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
