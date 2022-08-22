from scripts.utility import Utility as Util
from scripts.bot import discordBot
from pathlib import Path
from dotenv import dotenv_values
import discord, logging, os, sqlite3
from logging.handlers import TimedRotatingFileHandler


def main():
    # Initialization
    Path("./volume/logs").mkdir(parents=True, exist_ok=True)
    Path("./volume/gallery-dl").mkdir(parents=True, exist_ok=True)

    # TODO: Use local time
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logHandler = TimedRotatingFileHandler(
        os.path.join(os.getcwd(), "volume", "logs", "discord.log"),
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

    if Path("./.env").is_file():
        config = dotenv_values("./.env")
        token = config["DISCORD_TOKEN"]
    elif os.getenv("DISCORD_TOKEN"):
        token = os.getenv("DISCORD_TOKEN")
    else:
        raise ValueError(
            "Cannot find your discord token.\nPlease refer to my Github/DockerHub repository for help."
        )

    command_prefix = ">>"
    intents = discord.Intents(messages=True, guilds=True, members=True)
    activity = discord.Game(name=">>help")
    description = (
        "Discord bot for self use. \nWritten in Python, written by Reguna#9236."
    )
    bot = discordBot(command_prefix, intents, activity, description)

    logger.info("STARTING DISCORD BOT PROCESS...\n")
    bot.run(token)


if __name__ == "__main__":
    main()
