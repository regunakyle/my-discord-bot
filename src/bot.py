import logging
import os
import typing as ty
from inspect import getmembers, isclass

import discord
from discord.ext import commands
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from . import cogs, models

logger = logging.getLogger(__name__)


class discordBot(commands.Bot):
    def __init__(
        self,
        command_prefix: str,
        intents: discord.Intents,
        activity: discord.Game,
        description: str,
        sessionmaker: async_sessionmaker[AsyncSession],
    ):
        super().__init__(
            command_prefix=command_prefix,
            intents=intents,
            activity=activity,
            description=description,
        )
        # Disable prefixed help command, use /help instead
        self.help_command = None
        self.sessionmaker = sessionmaker

    async def setup_hook(self) -> None:
        logger.info(f"Logged in as {self.user.name} ({str(self.user.id)}).")

        # Add all cogs
        for module in getmembers(cogs, isclass):
            await self.add_cog(module[1](self, self.sessionmaker))

        async with self.sessionmaker() as session:
            # Delete removed guilds
            await session.execute(
                delete(models.GuildInfo).where(
                    ~models.GuildInfo.guild_id.in_([guild.id for guild in self.guilds])
                )
            )
            await session.commit()

    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info(
            f"Joined a new guild. Guild ID: {guild.id}; Guild Name: {guild.name}"
        )
        async with self.sessionmaker() as session:
            try:
                session.add(
                    models.GuildInfo(
                        guild_id=guild.id,
                        guild_name=guild.name,
                        bot_channel=guild.system_channel.id
                        if guild.system_channel
                        else None,
                    )
                )
                await session.commit()
            except Exception as e:
                print("Error adding guild to database:", e)
        if guild.system_channel:
            await guild.system_channel.send(
                "Hi everyone! Type `/help` to see all my available commands!"
            )

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        logger.info(f"Left a guild. Guild ID: {guild.id}; Guild Name: {guild.name}")
        async with self.sessionmaker() as session:
            # Delete removed guild from database
            await session.execute(
                delete(models.GuildInfo).where(models.GuildInfo.guild_id == guild.id)
            )
            await session.commit()

    async def on_member_join(self, member: discord.member) -> None:
        channel = member.guild.system_channel
        async with self.sessionmaker() as session:
            guild: models.GuildInfo | None = (
                await session.execute(
                    select(models.GuildInfo).where(
                        models.GuildInfo.guild_id == member.guild.id
                    )
                )
            ).scalar()
            if not guild:
                return

        if channel is not None and guild.welcome_message:
            try:
                await channel.send(f"<@{member.id}>\n{guild.welcome_message}")
            except Exception as e:
                # TODO: Delete the welcome message if the message is malformed
                logger.error(e)
