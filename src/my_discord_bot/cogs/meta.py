import logging
import os
import tomllib
from pathlib import Path

import discord
import pygit2
from discord.ext import commands
from sqlalchemy import delete, insert, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..exceptions import GuildNotFoundError
from ..models import Guild
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
        logger.info("sync: synced %d commands globally", len(synced))

        await ctx.send(f"Synced {len(synced)} commands globally.")

        # Sync database with joined guilds
        logger.info("sync: syncing %d guilds to database", len(self.bot.guilds))
        async with self.sessionmaker() as session:
            await session.execute(
                delete(Guild).where(
                    ~Guild.guild_id.in_([guild.id for guild in self.bot.guilds])
                )
            )

            for guild in self.bot.guilds:
                try:
                    await session.execute(
                        insert(Guild).values(guild_id=guild.id, guild_name=guild.name)
                    )
                except Exception:
                    pass

            await session.commit()
            logger.info("sync: guild database synced successfully")

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
                "title": "List of commands",
                "description": self.bot.description,
                "color": 65327,
                "author": {
                    "name": self.bot.application.name,
                    "url": "https://github.com/regunakyle/my-discord-bot",
                    "icon_url": self.bot.user.avatar.url,
                },
                "fields": [],
            }

            for key in self.bot.cogs.keys():
                field = {"name": key, "value": ""}
                for command in self.bot.cogs[key].get_app_commands():
                    field["value"] += f"`{command.name}` "
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
                        "name": parameter.name
                        + (" (REQUIRED)" if parameter.required else ""),
                        "value": parameter.description
                        if parameter.description
                        else "No description (yet).",
                    }
                )
            await ia.response.send_message(embed=discord.Embed.from_dict(embedDict))

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
            await ia.response.send_message(
                "ERROR: Your message is too long! Maximum 2000 characters allowed.",
                ephemeral=True,
            )
            return

        resp = ""
        async with self.sessionmaker() as session:
            if not message:
                await session.execute(
                    update(Guild)
                    .where(Guild.guild_id == ia.guild.id)
                    .values(welcome_message=None)
                )
                resp = "Welcome message cleared."

            else:
                unescaped_msg = message.encode("latin-1", "backslashreplace").decode(
                    "unicode-escape"
                )
                resp = f"Welcome message set. Example message:\n<@{ia.user.id}>\n{unescaped_msg}"

                if (
                    await session.execute(
                        update(Guild)
                        .where(Guild.guild_id == ia.guild.id)
                        .values(welcome_message=unescaped_msg)
                    )
                ).rowcount == 0:
                    raise GuildNotFoundError(ia.guild)

            await session.commit()
            logger.debug("set_welcome_message: committed guild=%s", ia.guild.name)

        await ia.response.send_message(resp)

    @discord.app_commands.command()
    async def version(self, ia: discord.Interaction) -> None:
        """Report the current version of the bot."""

        # If deploy via git, then both .git and pyproject.toml should exist.
        # If deploy via docker, then the environment variable VARIABLE should be set.

        git = Path("./.git")
        pyproject = Path("./pyproject.toml")
        version_template = "Current bot version: {version}"

        if os.getenv("APP_VERSION"):
            logger.debug("version: using APP_VERSION=%s", os.getenv("APP_VERSION"))
            await ia.response.send_message(
                version_template.format(version=os.getenv("APP_VERSION"))
            )
        elif (
            git.exists()
            and (repo := pygit2.Repository(str(git))).head.shorthand != "master"
        ):
            logger.debug(
                "version: using git branch=%s commit=%s",
                repo.head.shorthand,
                repo.revparse("HEAD").from_object.short_id,
            )
            await ia.response.send_message(
                version_template.format(
                    version=f"{repo.head.shorthand}-{repo.revparse('HEAD').from_object.short_id}"
                )
            )
        elif pyproject.exists():
            with open(pyproject, "rb") as toml:
                try:
                    version = tomllib.load(toml)["project"]["version"]
                    logger.debug("version: using pyproject.toml version=%s", version)
                    await ia.response.send_message(
                        version_template.format(version=version)
                    )
                except KeyError:
                    await ia.response.send_message(
                        "ERROR: Version not found in pyproject.toml!",
                        ephemeral=True,
                    )
        else:
            await ia.response.send_message(
                "ERROR: Version not found!",
                ephemeral=True,
            )
