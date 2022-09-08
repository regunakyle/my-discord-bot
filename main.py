from scripts.bot import discordBot
from pathlib import Path
from dotenv import dotenv_values
from scripts.utility import Utility as Util
import discord, logging, sqlite3
from logging.handlers import TimedRotatingFileHandler

# TODO: 3 Task(s)
# Dashboard (Quart)
# ORM
# os -> pathlib.Path


def main() -> None:
    # Initialization
    Path("./volume/logs").mkdir(parents=True, exist_ok=True)
    Path("./volume/gallery-dl").mkdir(parents=True, exist_ok=True)

    # Time Rotating File Handler
    # TODO: Use local time
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logHandler = TimedRotatingFileHandler(
        Path("./volume/logs/discord.log"),
        when="D",
        backupCount=10,
        encoding="utf-8",
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

        cnxn = sqlite3.connect("./volume/db.sqlite3")
        cursor = cnxn.cursor()
        for path in Path("./DB_scripts").rglob("*.sql"):
            with open(path, "r") as f:
                cursor.execute(f.read())
                cnxn.commit()
        cursor.close()
        cnxn.close()

    command_prefix = Util.getEnvVar("PREFIX")

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    activity = discord.Game(name=f"{command_prefix}help")

    description = (
        "Discord bot for self use. \nWritten in Python, written by Reguna#9236."
    )

    bot = discordBot(command_prefix, intents, activity, description)

    logger.info("STARTING DISCORD BOT PROCESS...\n")
    bot.run(Util.getEnvVar("DISCORD_TOKEN"))


if __name__ == "__main__":
    main()
