import asyncio
import logging
import os
import shutil
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import discord
from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import ConnectionPoolEntry

from src import discordBot, models


async def main() -> None:
    # Initialization
    Path("./volume/logs").mkdir(parents=True, exist_ok=True)
    Path("./volume/gallery-dl").mkdir(parents=True, exist_ok=True)
    if not Path("./volume/gallery-dl/config.json").is_file():
        try:
            shutil.copy2("./assets/gallery-dl/config.json", "./volume/gallery-dl")
        except:
            pass

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
    for env in ["DISCORD_TOKEN", "PREFIX", "DATABASE_CONNECTION_STRING"]:
        if not os.getenv(env):
            errMsg = f"{env} is not set in both .env and the OS environment. Exiting..."
            logger.error(errMsg)
            raise Exception(errMsg)

    # Database initialization
    engine = create_async_engine(os.getenv("DATABASE_CONNECTION_STRING"), echo=True)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(
        dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry
    ) -> None:
        """If using SQLite, enable foreign key constraints."""
        if os.getenv("DATABASE_CONNECTION_STRING").startswith(r"sqlite+aiosqlite://"):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(models.model_base.ModelBase.metadata.create_all)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    activity = discord.Game(name="/help")

    description = "Discord bot for self use. \nWritten in Python using discord.py."

    bot = discordBot(os.getenv("PREFIX"), intents, activity, description, async_session)

    logger.info("STARTING DISCORD BOT PROCESS...\n")
    await bot.start(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
