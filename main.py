from scripts.utility import utility as util
from datetime import datetime
from pathlib import Path
import configparser, discord, logging

if __name__ == "__main__":
    # Initialization
    if not Path("./volume").is_dir():
        util.print("Folder 'volume' not found. Beginning initialization...")
        Path("./volume/logs/").mkdir(parents=True, exist_ok=True)

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

    config = configparser.ConfigParser()
    config.read("./volume/app.cfg")
    try:
        token = config["Discord"]["Token"]
    except KeyError:
        util.print(
            "Cannot find your Discord token.\nPlease follow the instructions written in GitHub README.md."
        )
        quit()

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
