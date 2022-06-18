from discord.ext import commands
from ..utility import utility as util
import logging

# TODO: 4 task(s)
# Get into touhou guide
# Subscription to certain people, e.g. ZUN
# Ask trivia question; Validate answer
# Set/Remove trivia
logger = logging.getLogger(__name__)


class Touhou(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
