from scripts.bot import discordBot
from scripts.utility import utility as util
import logging
import discord
from datetime import datetime
import configparser

if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("app.cfg")

    logging.basicConfig(
        filename="./logs/" + util.strftime(datetime.now(), False) + ".log",
        encoding="utf-8",
        level=logging.DEBUG,
        format="%(asctime)s(%(levelname)s) - %(message)s",
        datefmt="%H:%M:%S",
    )

    logging.info("DISCORD BOT PROCESS STARTED\n")

    command_prefix = ">>"
    intents = discord.Intents(messages=True, guilds=True)
    activity = discord.Game(name=">>help")
    bot = discordBot(command_prefix, intents, activity)

    bot.run(config["Discord"]["Token"])
    logging.info("DISCORD BOT ENDED\n")
