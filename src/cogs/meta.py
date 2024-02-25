import datetime as dt
import logging
import typing as ty
from pathlib import Path

import discord
from discord.ext import commands
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .. import models
from ._cog_base import CogBase

logger = logging.getLogger(__name__)


class Meta(CogBase):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ) -> None:
        super().__init__(bot, sessionmaker)

    @commands.hybrid_command()
    async def sync(
        self,
        ctx: commands.Context,
    ) -> None:
        """(OWNER ONLY) Reload slash commands and sync guild info in database.

        Please run this once after every update!
        """
        logger.info("Syncing commands and guilds...")

        if not await self.bot.is_owner(ctx.author):
            await ctx.send("Only the bot owner may use this command!")
            return

        synced = await self.bot.tree.sync()

        await ctx.send(f"Synced {len(synced)} commands globally.")

        # Sync database with joined guilds
        async with self.sessionmaker() as session:
            await session.execute(
                delete(models.GuildInfo).where(
                    ~models.GuildInfo.guild_id.in_(
                        [guild.id for guild in self.bot.guilds]
                    )
                )
            )

            # TODO: Optimize
            for guild in self.bot.guilds:
                try:
                    await session.execute(
                        insert(models.GuildInfo).values(
                            guild_id=guild.id, guild_name=guild.name
                        )
                    )
                except Exception:
                    pass

            await session.commit()

    @discord.app_commands.command()
    @discord.app_commands.describe(
        command_name="Name of the command you want to check.",
    )
    async def help(
        self, ia: discord.Interaction, command_name: str | None = None
    ) -> None:
        """Display all available commands, or show the explanation of <command_name>."""
        if not command_name:
            embedDict = {
                "title": f"{self.bot.application.name}: Help",
                "description": f"{self.bot.description}",
                "color": 65327,
                "author": {
                    "name": "Reguna (reguna)",
                    "url": "https://github.com/regunakyle/my-discord-bot",
                    "icon_url": self.bot.get_user(263243377821089792).avatar.url,
                },
                "fields": [],
            }

            for key in self.bot.cogs.keys():
                field = {"name": key, "value": ""}
                for command in self.bot.cogs[key].get_app_commands():
                    field["value"] += f"{command.name} "
                if not field["value"]:
                    continue
                embedDict["fields"].append(field)

            await ia.response.send_message(embed=discord.Embed.from_dict(embedDict))
        else:
            command = self.bot.tree.get_command(command_name)
            if command is None:
                await ia.response.send_message(f"Command '{command_name}' not found.")
                return
            embedDict = {
                "title": f"/{command.name}",
                "description": command.description,
                "color": 65535,
                "fields": [],
            }
            for parameter in command.parameters:
                embedDict["title"] += (
                    f" [{parameter.name}]"
                    if parameter.required
                    else f" <{parameter.name}>"
                )
                embedDict["fields"].append(
                    {
                        "name": parameter.name,
                        "value": parameter.description
                        if parameter.description
                        else "No description (yet).",
                    }
                )
            await ia.response.send_message(embed=discord.Embed.from_dict(embedDict))

    @discord.app_commands.command()
    @discord.app_commands.checks.has_permissions(manage_channels=True)
    @discord.app_commands.guild_only()
    async def set_bot_channel(self, ia: discord.Interaction) -> None:
        """(ADMIN) Mark (or unmark) the current channel as the subscription channel."""
        resp = "Bot channel unset."
        async with self.sessionmaker() as session:
            if (
                await session.execute(
                    update(models.GuildInfo)
                    .where(models.GuildInfo.guild_id == ia.guild.id)
                    .where(models.GuildInfo.bot_channel == ia.channel.id)
                    .values(bot_channel=None)
                )
            ).rowcount == 0:
                await session.execute(
                    update(models.GuildInfo)
                    .where(models.GuildInfo.guild_id == ia.guild.id)
                    .values(bot_channel=ia.channel.id)
                )

                resp = f"Bot channel set to <#{ia.channel.id}>."
            await session.commit()
        await ia.response.send_message(resp)

    @discord.app_commands.command()
    @discord.app_commands.describe(
        number_of_days="Number of days from today",
    )
    async def get_log(self, ia: discord.Interaction, number_of_days: int = 0) -> None:
        """(OWNER ONLY) Get log file."""
        if not await self.bot.is_owner(ia.user):
            await ia.response.send_message("Only the bot owner may use this command!")
            return

        try:
            assert int(number_of_days) != 0
            dateString = dt.date.strftime(
                dt.date.today() + dt.timedelta(days=int(number_of_days)),
                r".%Y-%m-%d",
            )
        except Exception:
            dateString = ""

        fileName = f"discord.log{dateString}"
        link = Path(f"./volume/logs/{fileName}")
        if link.is_file():
            await ia.response.send_message(file=discord.File(link))
        else:
            await ia.response.send_message(
                f"File {fileName} not found.",
            )

    @discord.app_commands.command()
    @discord.app_commands.guild_only()
    @discord.app_commands.checks.has_permissions(manage_channels=True)
    @discord.app_commands.describe(
        message="Hint: NO double quotes; Linebreak: \\n; Self-explanatory: <#ChannelNumber>, <@UserID>, <a:EmojiName:EmojiID>"
    )
    async def set_welcome_message(
        self, ia: discord.Interaction, message: str = ""
    ) -> None:
        """(ADMIN) Set welcome message send to newcomers of this server. Unset if no message inputted."""
        # Special syntax
        # Channel: <#ChannelNumber>
        # User: <@UserID>
        # Emote: <a:EmoteName:EmoteID>
        if len(message) > 2000:
            await ia.response.send_message("Your message is too long!")
            return

        resp = ""
        async with self.sessionmaker() as session:
            if not message:
                await session.execute(
                    update(models.GuildInfo)
                    .where(models.GuildInfo.guild_id == ia.guild.id)
                    .values(welcome_message=None)
                )
                resp = "Welcome message cleared."

            else:
                unescaped_msg = message.encode("latin-1", "backslashreplace").decode(
                    "unicode-escape"
                )
                await session.execute(
                    update(models.GuildInfo)
                    .where(models.GuildInfo.guild_id == ia.guild.id)
                    .values(welcome_message=unescaped_msg)
                )
                resp = (
                    f"Welcome message set. Example:\n<@{ia.user.id}>\n{unescaped_msg}"
                )
            await session.commit()
        await ia.response.send_message(resp)

    @discord.app_commands.command()
    @discord.app_commands.guild_only()
    @discord.app_commands.checks.has_permissions(manage_channels=True)
    async def populate_thread(self, ia: discord.Interaction) -> None:
        """(ADMIN) Populate the current thread without pinging anyone. Only works if your guild has fewer than 1000 members."""

        if "thread" not in ia.channel.type.name:
            await ia.response.send_message("This channel is not a thread!")
            return
        if ia.guild.member_count >= 1000:
            await ia.response.send_message(
                "I cannot add this many people to a thread! (1000 members maximum per thread)"
            )
            return

        await ia.response.send_message(
            "Please wait a while I try to add everyone to this thread..."
        )

        resp = ""
        message = await ia.channel.send("Processing...")
        # This probably can be optimized
        for member in ia.guild.members:
            if not member.bot:
                resp += f"<@{member.id}>"
            if len(resp) >= 2000:
                await message.edit(content=resp[:2000])
                resp = f"<@{member.id}>"
        await message.edit(content=resp)
        await message.edit(content="Thread populated.")

    @discord.app_commands.command()
    @discord.app_commands.describe(
        message="NO double quotes. Hint: \\n, <#ChannelNumber>, <@UserID>, <a:EmojiName:EmojiID>",
    )
    async def broadcast(self, ia: discord.Interaction, message: str = "") -> None:
        """(OWNER ONLY) Send a message to every bot channel in database."""
        if not await self.bot.is_owner(ia.user):
            await ia.response.send_message("Only the bot owner may use this command!")
            return

        if len(message) > 2000:
            await ia.response.send_message("Your message is too long!")
            return

        async with self.sessionmaker() as session:
            channels: ty.List[int] = (
                await session.execute(select(models.GuildInfo.bot_channel))
            ).scalars()
            await ia.response.send_message("Broadcasting...")
            for channel in channels:
                try:
                    await self.bot.get_channel(channel).send(message)
                except Exception:
                    pass
