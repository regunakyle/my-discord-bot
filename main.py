import logging
import sqlite3
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import discord

from scripts.bot import discordBot
from scripts.utility import Utility as Util


def main() -> None:
    # Initialization
    Path("./volume/logs").mkdir(parents=True, exist_ok=True)
    Path("./volume/gallery-dl").mkdir(parents=True, exist_ok=True)

    # Time Rotating File Handler
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
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
    # Stream Handler
    logger.addHandler(logging.StreamHandler())

    if not Path("./volume/db.sqlite3").is_file():
        logger.info("Database not found. Creating sqlite database...")
        # Initialize database
        # Docker Python image uses Debain (aka old) version of SQLite, so cannot use STRICT keyword
        # See pysqlite3 (https://github.com/coleifer/pysqlite3)

        cnxn = sqlite3.connect("./volume/db.sqlite3")
        cursor = cnxn.cursor()
        for script in Path("./DB_scripts").rglob("*.sql"):
            with open(script, "r") as f:
                cursor.execute(f.read())
                cnxn.commit()
        cursor.close()
        cnxn.close()

    command_prefix = Util.getEnvVar("PREFIX")

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    activity = discord.Game(name="/help")

    description = "Discord bot for self use. \nWritten in Python using discord.py."

    bot = discordBot(command_prefix, intents, activity, description)

    logger.info("STARTING DISCORD BOT PROCESS...\n")
    bot.run(Util.getEnvVar("DISCORD_TOKEN"))


if __name__ == "__main__":
    main()
