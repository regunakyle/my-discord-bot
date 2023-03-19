import logging
import os
import typing as ty
from inspect import getmembers, isclass
from pathlib import Path

import discord
from discord.ext import commands
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

    async def on_ready(self) -> None:
        logger.info(f"Logged in as {self.user.name} ({str(self.user.id)}).")

        # Add all cogs
        for module in getmembers(cogs, isclass):
            await self.add_cog(module[1](self, self.sessionmaker))

        # Add all guilds into database
        async with self.sessionmaker() as session:
            guilds = []
            for guild in self.guilds:
                guilds.append(
                    models.GuildInfo(guild_id=guild.id, guild_name=guild.name)
                )
            session.add_all(guilds)
            await session.commit()

    async def on_member_join(self, member: discord.member) -> None:
        # TODO: Make this dynamic
        channel = member.guild.system_channel
        if channel is not None:
            if member.guild.id in [651435165012459520, 1000302465276710943]:
                await channel.send(f"<@{member.id}>\nWelcome!")
            if member.guild.id == 200911777721090057:
                await channel.send(
                    f"<@{member.id}>\n歡迎加入本鄉!\n請先閱讀<#315162071945838592> <#680349727510102036> <#591934638964998144>並選取合適之身份組!"
                )
