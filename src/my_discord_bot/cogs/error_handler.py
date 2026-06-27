import logging
import typing as ty
from pathlib import Path

import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..exceptions import GuildNotFoundError
from ..models import Guild
from ._cog_base import CogBase

logger = logging.getLogger(__name__)


class ErrorHandler(CogBase):
    """A cog for global error handling."""

    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ) -> None:
        super().__init__(bot, sessionmaker)
        self.bot.tree.on_error = self.on_app_command_error

    async def on_app_command_error(
        self, ia: discord.Interaction, e: discord.app_commands.AppCommandError
    ) -> None:
        """Called when uncaught exceptions in other commands are raised."""

        logger.error(e)
        error: ty.Dict[str, ty.Any] = {"content": None}

        if isinstance(e, discord.app_commands.MissingPermissions):
            error["content"] = "ERROR: You don't have the required permission!"
        elif isinstance(e, discord.app_commands.NoPrivateMessage):
            error["content"] = "ERROR: This command is only available inside a server!"
        elif isinstance(e, discord.app_commands.CommandOnCooldown):
            error["content"] = str(e) + "."
        elif isinstance(
            e, discord.app_commands.CommandInvokeError
        ) and "error code: 40005" in str(e):
            error["content"] = (
                "ERROR: I tried to upload a huge file and was rejected by Discord! (Maximum size: {size}MiB)".format(
                    size=self.get_max_file_size(ia.guild)
                )
            )
        elif isinstance(e, discord.app_commands.CommandInvokeError):
            # Unwrap the original exception from CommandInvokeError
            original = e.original

            if isinstance(original, GuildNotFoundError):
                # Insert the guild into the database so the user can retry
                async with self.sessionmaker() as session:
                    try:
                        session.add(
                            Guild(
                                guild_id=ia.guild.id,
                                guild_name=ia.guild.name,
                            )
                        )
                        await session.commit()
                    except Exception:
                        logger.error("Failed to add guild to database.", exc_info=True)
                error["content"] = (
                    "ERROR: The guild was not in my database. I've added it now — please try running the command again!"
                )
            else:
                error["content"] = "ERROR: Something unexpected happened!"
                error["file"] = discord.File(Path("./assets/images/error.jpg"))
        else:
            error["content"] = "ERROR: Something unexpected happened!"
            error["file"] = discord.File(Path("./assets/images/error.jpg"))

        try:
            await ia.response.send_message(**error, ephemeral=True)
        except discord.errors.InteractionResponded:
            await ia.followup.send(**error, ephemeral=True)
