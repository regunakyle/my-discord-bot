from discord.ext import commands
from ..utility import Utility as Util
import logging

logger = logging.getLogger(__name__)


class Touhou(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
