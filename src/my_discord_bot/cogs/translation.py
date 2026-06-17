import io
import logging
import typing as ty

import aiohttp
import discord
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import joinedload

from ..exceptions import GuildNotFoundError
from ..models import Guild
from ..models import Translation as tl_model
from ._cog_base import CogBase

logger = logging.getLogger(__name__)

ACK_EMOJI = "✅"  # Placeholder — bot owner will change this


class Translation(CogBase):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ) -> None:
        super().__init__(bot, sessionmaker)

    # ── Slash commands ──────────────────────────────────────────────

    @discord.app_commands.command(name="translation_setup")
    @discord.app_commands.guild_only()
    @discord.app_commands.checks.has_permissions(manage_channels=True)
    @discord.app_commands.describe(
        emote="Trigger emoji (e.g. <a:name:id>, <:name:id>, or 🔄)",
        chinese_channel="Channel for Chinese messages",
        english_channel="Channel for English messages",
    )
    async def translation_setup(
        self,
        ia: discord.Interaction,
        emote: str,
        chinese_channel: discord.TextChannel,
        english_channel: discord.TextChannel,
    ) -> None:
        """Configure translation between two channels."""
        if chinese_channel.id == english_channel.id:
            await ia.response.send_message(
                "ERROR: Chinese and English channels must be different!",
                ephemeral=True,
            )
            return

        async with self.sessionmaker() as session:
            guild_row = (
                await session.execute(
                    select(Guild)
                    .options(joinedload(Guild.translation))
                    .where(Guild.guild_id == ia.guild.id)
                )
            ).scalar_one_or_none()

            if guild_row is None:
                raise GuildNotFoundError(ia.guild)

            if guild_row.translation is not None:
                guild_row.translation.trigger_emote = emote
                guild_row.translation.chinese_channel_id = chinese_channel.id
                guild_row.translation.english_channel_id = english_channel.id
            else:
                guild_row.translation = tl_model(
                    trigger_emote=emote,
                    chinese_channel_id=chinese_channel.id,
                    english_channel_id=english_channel.id,
                )

            try:
                await session.commit()
            except IntegrityError as e:
                await session.rollback()
                logger.error("Integrity error in translation_setup:", e)
                await ia.response.send_message(
                    "ERROR: Failed to save configuration. Please try again.",
                    ephemeral=True,
                )
                return

        await ia.response.send_message(
            f"Translation configured!\n"
            f"Trigger emote: {emote}\n"
            f"Chinese channel: {chinese_channel.mention}\n"
            f"English channel: {english_channel.mention}",
            ephemeral=True,
        )

    @discord.app_commands.command(name="translation_status")
    @discord.app_commands.guild_only()
    async def translation_status(self, ia: discord.Interaction) -> None:
        """Show current translation configuration."""
        async with self.sessionmaker() as session:
            guild_row = (
                await session.execute(
                    select(Guild)
                    .options(joinedload(Guild.translation))
                    .where(Guild.guild_id == ia.guild.id)
                )
            ).scalar_one_or_none()

            if guild_row is None:
                raise GuildNotFoundError(ia.guild)

            translation = guild_row.translation

        if translation is None:
            await ia.response.send_message(
                "Translation is not configured for this server.",
                ephemeral=True,
            )
            return

        chinese_channel = ia.guild.get_channel(translation.chinese_channel_id)
        english_channel = ia.guild.get_channel(translation.english_channel_id)

        await ia.response.send_message(
            f"**Translation Configuration**\n"
            f"Trigger emote: {translation.trigger_emote}\n"
            f"Chinese channel: {chinese_channel.mention if chinese_channel else 'Channel not found'}\n"
            f"English channel: {english_channel.mention if english_channel else 'Channel not found'}",
            ephemeral=True,
        )

    @discord.app_commands.command(name="translation_reset")
    @discord.app_commands.guild_only()
    @discord.app_commands.checks.has_permissions(manage_channels=True)
    async def translation_reset(self, ia: discord.Interaction) -> None:
        """Reset translation configuration."""
        async with self.sessionmaker() as session:
            guild_row = (
                await session.execute(
                    select(Guild)
                    .options(joinedload(Guild.translation))
                    .where(Guild.guild_id == ia.guild.id)
                )
            ).scalar_one_or_none()

            if guild_row is None:
                raise GuildNotFoundError(ia.guild)

            if guild_row.translation is not None:
                await session.delete(guild_row.translation)
                await session.commit()

        await ia.response.send_message(
            "Translation configuration has been reset.",
            ephemeral=True,
        )

    # ── Listeners ───────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_reaction_add(
        self, reaction: discord.Reaction, user: discord.User
    ) -> None:
        """Handle trigger emote reactions to start translation."""
        if user.bot:
            return
        if not reaction.message.guild:
            return

        # Load config
        translation = await self._get_translation(reaction.message.guild)
        if translation is None:
            return

        # Match trigger emote
        if str(reaction.emoji) != translation.trigger_emote:
            return

        # Check channel
        if reaction.message.channel.id not in (
            translation.chinese_channel_id,
            translation.english_channel_id,
        ):
            return

        # Ack check — skip if already processed
        for r in reaction.message.reactions:
            if str(r.emoji) == ACK_EMOJI:
                return

        # Add ack
        try:
            await reaction.message.add_reaction(ACK_EMOJI)
        except discord.HTTPException:
            return

        # Determine direction
        source_channel = reaction.message.channel
        if source_channel.id == translation.chinese_channel_id:
            target_language = "English"
            target_channel_id = translation.english_channel_id
        else:
            target_language = "Traditional Chinese"
            target_channel_id = translation.chinese_channel_id

        target_channel = reaction.message.guild.get_channel(target_channel_id)
        if target_channel is None or not isinstance(
            target_channel, discord.abc.Messageable
        ):
            logger.error(f"Target channel {target_channel_id} not found.")
            return

        # Build translated message
        text = reaction.message.content
        if text:
            messages = [
                {
                    "role": "system",
                    "content": (
                        f"You are a translator. Translate the following text to {target_language}. "
                        f"Output ONLY the translated text, nothing else."
                    ),
                },
                {"role": "user", "content": text},
            ]
            translated = await self.call_openai(messages)
            if translated is None:
                await reaction.message.channel.send(
                    "Translation failed. Please try again later."
                )
                return
            content_text = translated[:2000]
        else:
            # Empty text (embed/attachment only) — forward as-is
            content_text = None

        # Compose message
        author_name = reaction.message.author.display_name
        source_name = source_channel.name
        header = f"[TRANSLATION] forwarded from #{source_name} by {author_name}"

        if content_text is not None:
            embed = discord.Embed(description=content_text)
        else:
            embed = discord.Embed(description="*(forwarded as-is)*")
        embed.set_author(name=header)

        # Collect attachments
        files: list[discord.File] = []
        async with aiohttp.ClientSession() as http:
            for attachment in reaction.message.attachments:
                try:
                    async with http.get(attachment.url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            files.append(
                                discord.File(
                                    io.BytesIO(data),
                                    filename=attachment.filename,
                                )
                            )
                except Exception as e:
                    logger.error(f"Failed to download attachment: {e}")

        try:
            if content_text is None:
                # For empty-text messages, forward original embeds alongside ours
                all_embeds = [embed] + reaction.message.embeds
            else:
                all_embeds = [embed]

            await ty.cast(discord.abc.Messageable, target_channel).send(
                embeds=all_embeds,
                files=files,
            )
        except discord.HTTPException as e:
            logger.error(f"Failed to send translation: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Handle replies to [TRANSLATION] messages for reply chains."""
        if message.author.bot:
            return
        if not message.guild:
            return

        # Check for reply
        if not message.reference or not message.reference.resolved:
            return

        resolved = message.reference.resolved
        if not resolved.author.bot:
            return

        # Check for [TRANSLATION] flag
        if not resolved.content.startswith("[TRANSLATION]"):
            return

        # Load config
        translation = await self._get_translation(message.guild)
        if translation is None:
            return

        # Verify channel
        if message.channel.id not in (
            translation.chinese_channel_id,
            translation.english_channel_id,
        ):
            return

        # Determine direction
        source_channel = message.channel
        if source_channel.id == translation.chinese_channel_id:
            target_language = "English"
            target_channel_id = translation.english_channel_id
        else:
            target_language = "Traditional Chinese"
            target_channel_id = translation.chinese_channel_id

        target_channel = message.guild.get_channel(target_channel_id)
        if target_channel is None or not isinstance(
            target_channel, discord.abc.Messageable
        ):
            logger.error(f"Target channel {target_channel_id} not found.")
            return

        # Translate
        text = message.content
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a translator. Translate the following text to {target_language}. "
                    f"Output ONLY the translated text, nothing else."
                ),
            },
            {"role": "user", "content": text},
        ]
        translated = await self.call_openai(messages)
        if translated is None:
            # Log error silently for reply-triggered translations
            return

        content_text = translated[:2000]

        # Compose message
        author_name = message.author.display_name
        source_name = source_channel.name
        header = f"[TRANSLATION] forwarded from #{source_name} by {author_name}"

        embed = discord.Embed(description=content_text)
        embed.set_author(name=header)

        # Collect attachments
        files: list[discord.File] = []
        async with aiohttp.ClientSession() as http:
            for attachment in message.attachments:
                try:
                    async with http.get(attachment.url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            files.append(
                                discord.File(
                                    io.BytesIO(data),
                                    filename=attachment.filename,
                                )
                            )
                except Exception as e:
                    logger.error(f"Failed to download attachment: {e}")

        try:
            await ty.cast(discord.abc.Messageable, target_channel).send(
                embed=embed,
                files=files,
            )
        except discord.HTTPException as e:
            logger.error(f"Failed to send translation: {e}")

    # ── Helpers ─────────────────────────────────────────────────────

    async def _get_translation(self, guild: discord.Guild) -> ty.Optional[tl_model]:
        """Fetch the Translation row for a guild via the relationship."""
        async with self.sessionmaker() as session:
            guild_row = (
                await session.execute(
                    select(Guild)
                    .options(joinedload(Guild.translation))
                    .where(Guild.guild_id == guild.id)
                )
            ).scalar_one_or_none()

            return guild_row.translation if guild_row else None
