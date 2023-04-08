import logging
import typing as ty
from pathlib import Path

import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .cog_base import CogBase

logger = logging.getLogger(__name__)


class ErrorHandler(CogBase):
    """A cog for global error handling."""

    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ):
        super().__init__(bot, sessionmaker)
        self.bot.tree.on_error = self.on_app_command_error

    async def on_app_command_error(
        self, ia: discord.Interaction, e: discord.app_commands.AppCommandError
    ) -> None:
        logger.error(e)
        error = {"content": None}

        if isinstance(e, discord.app_commands.MissingPermissions):
            error["content"] = "You don't have the required permission!"
        elif isinstance(e, discord.app_commands.NoPrivateMessage):
            error["content"] = "This command is only available inside a server!"
        elif isinstance(e, discord.app_commands.CommandOnCooldown):
            error["content"] = "This command is on cooldown!"
        else:
            error["content"] = "Oh no! Something unexpected happened!"
            error["file"] = discord.File(Path("./assets/images/error.jpg"))

        try:
            await ia.response.send_message(**error)
        except discord.errors.InteractionResponded:
            await ia.followup.send(**error)
