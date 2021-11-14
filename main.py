from scripts.utility import utility as util
from datetime import datetime
from pathlib import Path
from dotenv import dotenv_values
import discord, logging, os

if __name__ == "__main__":
    # Initialization
    if not Path("./volume").is_dir():
        util.print("Folder 'volume' not found. Beginning initialization...")
        Path("./volume").mkdir(parents=True, exist_ok=True)

    if not Path("./volume/logs").is_dir():
        Path("./volume/logs").mkdir(parents=True, exist_ok=True)

    if not Path("./volume/db.sqlite3").is_file():
        util.print("Database not found. Creating sqlite database...")
        # Initialize database
        import sqlite3

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
            "Cannot find your discord token.\nPlease refer to my Github/Dockerhub repo for help."
        )

    logging.basicConfig(
        filename="./volume/logs/" + util.strftime(datetime.now(), False) + ".log",
        encoding="utf-8",
        level=logging.DEBUG,
        format="%(asctime)s(%(levelname)s) - %(message)s",
        datefmt="%H:%M:%S",
    )

    logging.info("DISCORD BOT PROCESS STARTED\n")

    from scripts.bot import discordBot

    command_prefix = ">>"
    intents = discord.Intents(messages=True, guilds=True)
    activity = discord.Game(name=">>help")
    bot = discordBot(command_prefix, intents, activity)

    bot.run(token)
    logging.info("DISCORD BOT ENDED\n")
