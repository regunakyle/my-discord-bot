import asyncio
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import discord
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import ConnectionPoolEntry

from .bot import DiscordBot

# Initialization
Path("./volume/logs").mkdir(parents=True, exist_ok=True)
Path("./volume/gallery-dl").mkdir(parents=True, exist_ok=True)

# Logger
logger = logging.getLogger()
logger.setLevel("INFO")
logger.addHandler(logging.StreamHandler())
# Time Rotating File Handler
logHandler = TimedRotatingFileHandler(
    Path("./volume/logs/discord.log"), when="D", backupCount=10, encoding="utf-8"
)
logHandler.setFormatter(
    logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)-15s %(message)s",
        datefmt="%H:%M:%S",
    )
)
logger.addHandler(logHandler)


# Load .env and basic sanity checking
load_dotenv(dotenv_path="./.env")
for env in ["DISCORD_TOKEN", "PREFIX"]:
    if not os.getenv(env):
        errMsg = f"{env} is not set in both .env and the OS environment. Exiting..."
        logger.error(errMsg)
        raise Exception(errMsg)

logging.info("Running migrations...")
alembic_cfg = Config("./alembic.ini")
alembic_cfg.attributes["no_alembic_loggers"] = True
command.upgrade(alembic_cfg, "head")


async def main() -> None:
    """Entrypoint of the bot."""

    logging.info("\nSetting up the bot...")

    # Database initialization
    engine = create_async_engine("sqlite+aiosqlite:///volume/db.sqlite3", echo=True)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(
        dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry
    ) -> None:
        """If using SQLite, enable foreign key constraints."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    activity = discord.Game(name="/help")

    description = "Discord bot my own use. \nCreated with [discord.py](https://github.com/Rapptz/discord.py)."

    bot = DiscordBot(
        os.getenv("PREFIX", ">>"), intents, activity, description, async_session
    )

    await bot.start(os.getenv("DISCORD_TOKEN", ""))


asyncio.run(main())
