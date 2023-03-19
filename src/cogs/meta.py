import datetime as dt
import logging
import typing as ty
from pathlib import Path

import discord
from discord.ext import commands
from sqlalchemy import select, update

from .. import models
from .cog_base import CogBase

logger = logging.getLogger(__name__)


class Meta(CogBase):
    @commands.command()
    @commands.guild_only()
    async def sync(
        self,
        ctx: commands.Context,
        guilds: commands.Greedy[discord.Object],
        spec: ty.Optional[ty.Literal["~", "*", "^"]] = None,
    ) -> None:
        """Reload application commands (i.e. slash commands).
        Only the owner of the bot may use this command.
        Please use this once after every update!
        """
        logger.info(f"sync {spec+' ' if spec else ''}invoked.")

        if not await self.bot.is_owner(ctx.author):
            await ctx.send("Only the bot owner may use this command!")
            return

        if not guilds:
            if spec == "~":
                # sync current guild, for guild specific commands
                synced = await self.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                # copies all global app commands to current guild and syncs
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                # clears all commands from the current guild target and syncs
                # (removes guild commands)
                self.bot.tree.clear_commands(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                # global sync
                synced = await self.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return

        # <prefix>sync id_1 id_2 -> syncs guilds with id 1 and 2
        ret = 0
        for guild in guilds:
            try:
                await self.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

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
                    "name": "Reguna (@Reguna#9236)",
                    "url": "https://github.com/regunakyle/MyDiscordBot",
                    "icon_url": "https://pbs.twimg.com/media/Fb0DzG9WIAALL2U?format=jpg&name=small",
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
            if command == None:
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
    @discord.app_commands.describe(
        is_unset="Set to True if you want to unmark the subscription channel.",
    )
    async def set_bot_channel(
        self, ia: discord.Interaction, is_unset: bool = False
    ) -> None:
        """Mark the current channel as the subscription channel. All notification will be sent here."""
        try:
            async with self.sessionmaker() as session:
                if is_unset:
                    self.runSQL(
                        """UPDATE GuildInfo SET BotChannel = null WHERE GuildId = ?""",
                        [ia.guild.id],
                    )
                else:
                    self.runSQL(
                        "INSERT OR REPLACE INTO GuildInfo VALUES (?,?,?,Datetime())",
                        [ia.guild.id, ia.guild.name, ia.channel.id],
                    )
                await ia.response.send_message("Update complete.")
        except Exception as e:
            logger.error(e)
            await ia.response.send_message("Operation failed. Something went wrong.")

    @discord.app_commands.command()
    @discord.app_commands.describe(
        number_of_days="Number of days from today",
    )
    async def get_log(self, ia: discord.Interaction, number_of_days: int = 0) -> None:
        """Get log file. Only the owner of the bot can use this."""
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
    @discord.app_commands.describe(message="PLACEHOLDER")
    async def set_welcome_message(
        self, ia: discord.Interaction, message: str = ""
    ) -> None:
        """Your message must not contain double quotes."""
        # Special syntax
        # Channel: <#ChannelNumber>
        # User: <@UserID>
        # Emote: <a:EmoteName:EmoteID>
        resp = ""
        if len(message) > 2000:
            await ia.response.send_message("Your message is too long!")
            return

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
                if (
                    await session.execute(
                        select(models.GuildInfo).where(
                            models.GuildInfo.guild_id == ia.guild.id
                        )
                    )
                ).first():
                    await session.execute(
                        update(models.GuildInfo)
                        .where(models.GuildInfo.guild_id == ia.guild.id)
                        .values(welcome_message=unescaped_msg)
                    )
                else:
                    session.add(
                        models.GuildInfo(
                            guild_id=ia.guild.id,
                            guild_name=ia.guild.name,
                            welcome_message=unescaped_msg,
                        )
                    )
                resp = "Welcome message set."
            await session.commit()
        await ia.response.send_message(resp)
