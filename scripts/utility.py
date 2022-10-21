import sqlite3, logging, typing as ty, os
from dotenv import dotenv_values
from pathlib import Path

logger = logging.getLogger(__name__)

# TODO: Use async SQLite3 library
class Utility:
    dotenv = dotenv_values(Path("./.env"))

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

    @classmethod
    def runSQL(
        cls, query: str, param: ty.List[ty.Any] | None = None
    ) -> ty.List[ty.Dict[str, ty.Any]] | None:
        """Run a SQL query and return the result as list of rows(as dict),

        or return None if no rows are returned.

        You should only run one SQL statement with each call to this function.
        """
        cnxn, cursor = cls.connectDB(cls)

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

    @classmethod
    def getEnvVar(cls, paramName: str) -> str | None:
        """Get the environment variable from .env file.

        If not found in the file (or if .env does not exist), get it from system variables instead.
        """
        if paramName in cls.dotenv:
            return cls.dotenv[paramName]
        return os.getenv(paramName)
