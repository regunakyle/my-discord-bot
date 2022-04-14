from scripts.utility import utility as util
from scripts.bot import discordBot
from datetime import datetime
from pathlib import Path
from dotenv import dotenv_values
import discord, logging, os, sqlite3


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
            "Cannot find your discord token.\nPlease refer to my Github/DockerHub repo for help."
        )

    # TODO: Daily rotating logging
    logging.basicConfig(
        filename="./volume/logs/" + util.strftime(datetime.now(), False) + ".log",
        level=logging.DEBUG,
        format="%(asctime)s(%(levelname)s) - %(message)s",
        datefmt="%H:%M:%S",
    )

    command_prefix = ">>"
    intents = discord.Intents(messages=True, guilds=True)
    activity = discord.Game(name=">>help")
    bot = discordBot(command_prefix, intents, activity)

    logging.info("STARTING DISCORD BOT PROCESS...\n")
    bot.run(token)
    logging.info("ENDING DISCORD BOT PROCESS...\n")