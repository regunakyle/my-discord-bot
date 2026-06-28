import asyncio
import logging
import re
import typing as ty
import uuid

import discord
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import joinedload

from ..constants import (
    ACK_EMOJI,
    DISCORD_MAX_MESSAGE_LENGTH,
    STREAM_EDIT_INTERVAL,
    TRANSLATION_HEADER_PREFIX,
    TRANSLATION_HEADER_TEMPLATE,
)
from ..exceptions import GuildNotFoundError
from ..models import Guild
from ..models import Translation as tl_model
from ._cog_base import CogBase

logger = logging.getLogger(__name__)

# Regex to extract channel ID from <#123456789> format
_CHANNEL_ID_RE = re.compile(r"<#(\d+)>")


def _build_header(chain_id: str, source_channel_id: int, user_name: str) -> str:
    """Build a translation header string."""
    return TRANSLATION_HEADER_TEMPLATE.format(chain_id, source_channel_id, user_name)


def _parse_header(header: str) -> tuple[str, int, str] | None:
    """Parse a translation header.

    Returns (chain_id, source_channel_id, user_name) or None.
    """
    if not header.startswith(TRANSLATION_HEADER_PREFIX):
        return None

    rest = header[len(TRANSLATION_HEADER_PREFIX) :]
    parts = rest.split(" | ")
    if len(parts) < 3:
        return None

    chain_id = parts[0].strip()

    channel_match = _CHANNEL_ID_RE.search(parts[1])
    if not channel_match:
        return None

    user_name = parts[2].strip()
    return chain_id, int(channel_match.group(1)), user_name


class Translation(CogBase):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ) -> None:
        super().__init__(bot, sessionmaker)

    # ── Helpers ─────────────────────────────────────────────────────

    async def _stream_translate(
        self,
        target_channel: discord.abc.Messageable,
        openai_messages: list[dict[str, str]],
        header: str,
    ) -> None:
        """Stream a translation into target_channel, splitting across reply messages if needed.

        Sends an initial plain-text message with the header, then edits in real-time as chunks arrive.
        When the text exceeds 2000 characters, a new reply message is created for the next block.
        """

        logger.debug("Starting translation stream, header=%s", header)

        # Initial "Translating..." message
        initial_content = f"{header}\nTranslating..."
        current_message = await ty.cast(
            discord.abc.Messageable,
            target_channel,
        ).send(initial_content)

        full_text = ""
        last_edit_time = asyncio.get_running_loop().time()
        current_block = 0
        # Each block carries the header, so reserve that space from the limit
        header_overhead = len(header) + 1  # +1 for the "\n"
        available_length = DISCORD_MAX_MESSAGE_LENGTH - header_overhead

        def _build_content(text: str) -> str:
            return f"{header}\n{text}"

        try:
            async for chunk in self.call_openai_stream(openai_messages):
                full_text += chunk

                # Check if we've crossed into a new block
                new_block = len(full_text) // available_length
                if new_block > current_block:
                    logger.debug(
                        "Crossed block boundary: block %d -> %d",
                        current_block,
                        new_block,
                    )
                    # Finalize the current block on the active message
                    block_start = current_block * available_length
                    block_text = full_text[block_start : block_start + available_length]
                    await current_message.edit(content=_build_content(block_text))

                    # Send a new reply message for the next block (also with header)
                    current_message = await ty.cast(
                        discord.abc.Messageable,
                        target_channel,
                    ).send(
                        _build_content("Loading..."),
                        reference=current_message,
                    )
                    current_block = new_block

                now = asyncio.get_running_loop().time()
                if now - last_edit_time >= STREAM_EDIT_INTERVAL:
                    block_start = current_block * available_length
                    block_text = full_text[block_start : block_start + available_length]
                    await current_message.edit(content=_build_content(block_text))
                    last_edit_time = now
        except Exception:
            logger.error("Error during translation", exc_info=True)

        # Final edit with the complete text for the last block
        logger.debug(
            "Stream complete, total length=%d, blocks=%d",
            len(full_text),
            current_block + 1,
        )
        if full_text:
            block_start = current_block * available_length
            block_text = full_text[block_start : block_start + available_length]
            await current_message.edit(content=_build_content(block_text))
        else:
            await current_message.edit(
                content=f"{header}\nTranslation failed. Please try again later."
            )

    async def _get_translation(self, guild: discord.Guild) -> tl_model | None:
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

    async def _translate_and_send(
        self,
        text: str,
        target_language: str,
        target_channel: discord.abc.Messageable,
        header: str,
    ) -> None:
        """Build the OpenAI prompt and stream the translation into target_channel."""
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a translator. Translate the following text to {target_language}."
                    f"Only output the translated result without any additional explanation."
                ),
            },
            {"role": "user", "content": text},
        ]
        try:
            await self._stream_translate(
                target_channel,
                messages,
                header,
            )
        except discord.HTTPException as e:
            logger.error("Failed to send translation: %s", e)

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

        # Skip if the message is already in the english channel
        if reaction.message.channel.id == translation.english_channel_id:
            return

        # Ack check — skip if already processed
        for r in reaction.message.reactions:
            if str(r.emoji) == ACK_EMOJI and r.me:
                return

        # Add ack
        try:
            await reaction.message.add_reaction(ACK_EMOJI)
        except discord.HTTPException as e:
            logger.error("Failed to add ack reaction: %s", e)
            return

        # Resolve target channel from DB config
        target_channel = reaction.message.guild.get_channel(
            translation.english_channel_id
        )
        if target_channel is None or not isinstance(
            target_channel, discord.abc.Messageable
        ):
            logger.error(
                "English channel %s not found.", translation.english_channel_id
            )
            return

        logger.debug(
            "on_reaction_add: translating %s -> English",
            reaction.message.channel.name,
        )

        # Compose header with chain ID, source channel, original user name
        chain_id = uuid.uuid4().hex[:8]
        header = _build_header(
            chain_id,
            reaction.message.channel.id,
            reaction.message.author.name,
        )

        # Translate
        text = reaction.message.content
        if text:
            logger.debug("on_reaction_add: translating text (%d chars)", len(text))
            await self._translate_and_send(text, "English", target_channel, header)

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
        # Exit if user not replying to bot
        if resolved.author.id != self.bot.user.id:
            return

        # Check for [TRANSLATION] flag and parse header
        first_line = resolved.content.split("\n")[0]
        parsed = _parse_header(first_line)
        if parsed is None:
            return

        chain_id, source_channel_id, _user_name = parsed
        logger.debug("on_message: matched chain %s", chain_id)

        # Load config for english channel
        translation = await self._get_translation(message.guild)
        if translation is None:
            return

        english_channel_id = translation.english_channel_id

        # Determine direction based on which channel the reply is in
        if message.channel.id == english_channel_id:
            target_language = "Traditional Chinese"
            target_channel_id = source_channel_id
        elif message.channel.id == source_channel_id:
            target_language = "English"
            target_channel_id = english_channel_id
        else:
            return

        target_channel = message.guild.get_channel(target_channel_id)
        if target_channel is None or not isinstance(
            target_channel, discord.abc.Messageable
        ):
            logger.error("Target channel %s not found.", target_channel_id)
            return

        # Reuse the same header
        header = _build_header(chain_id, source_channel_id, _user_name)

        # Translate
        text = message.content
        logger.debug(
            "on_message: translating %s -> %s (%d chars)",
            message.channel.name,
            target_language,
            len(text),
        )
        await self._translate_and_send(text, target_language, target_channel, header)

    # ── Slash commands ──────────────────────────────────────────────

    @discord.app_commands.command(name="translation_setup")
    @discord.app_commands.guild_only()
    @discord.app_commands.checks.has_permissions(manage_channels=True)
    @discord.app_commands.describe(
        emote="Trigger emoji (e.g. <a:name:id>, <:name:id>, or 🔄)",
        english_channel="Channel where English translations are posted",
    )
    async def translation_setup(
        self,
        ia: discord.Interaction,
        emote: str,
        english_channel: discord.TextChannel,
    ) -> None:
        """Configure translation to an English channel."""
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
                guild_row.translation.english_channel_id = english_channel.id
            else:
                guild_row.translation = tl_model(
                    trigger_emote=emote,
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
            f"English channel: {english_channel.mention}",
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
            )
            return

        english_channel = ia.guild.get_channel(translation.english_channel_id)

        await ia.response.send_message(
            f"**Translation Configuration**\n"
            f"Trigger emote: {translation.trigger_emote}\n"
            f"English channel: {english_channel.mention if english_channel else 'Channel not found'}",
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
        )
