import asyncio
import logging
import typing as ty

import discord
from discord.ext import commands
from discord.guild import TextChannel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..constants import DISCORD_MAX_MESSAGE_LENGTH, STREAM_EDIT_INTERVAL
from ._cog_base import CogBase, check_cooldown_factory

logger = logging.getLogger(__name__)

# TODO: Handle bad connections


class AI(CogBase):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ) -> None:
        super().__init__(bot, sessionmaker)

    @discord.app_commands.command()
    @discord.app_commands.checks.dynamic_cooldown(check_cooldown_factory(1.5))
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(
        message="Message to the AI.",
    )
    async def chat(
        self,
        ia: discord.Interaction,
        message: str,
    ) -> None:
        """(RATE LIMITED) Chat with AI."""
        await ia.response.defer()

        # Send initial message, we'll edit it as chunks arrive
        current_message = await ia.followup.send("Thinking...", wait=True)

        full_text = ""
        last_edit_time = asyncio.get_running_loop().time()
        current_block = 0

        try:
            async for chunk in self.call_openai_stream(
                [{"role": "user", "content": message}]
            ):
                full_text += chunk

                # Check if we've crossed into a new 2000-char block
                new_block = len(full_text) // DISCORD_MAX_MESSAGE_LENGTH
                if new_block > current_block:
                    # Finalize the current block on the active message
                    block_start = current_block * DISCORD_MAX_MESSAGE_LENGTH
                    block_text = full_text[
                        block_start : block_start + DISCORD_MAX_MESSAGE_LENGTH
                    ]
                    await current_message.edit(content=block_text)

                    # Send a new reply message for the next block
                    current_message: discord.Message = await ty.cast(
                        TextChannel, ia.channel
                    ).send(
                        "Loading...",
                        reference=current_message.to_reference(),
                    )
                    current_block = new_block

                now = asyncio.get_running_loop().time()
                if now - last_edit_time >= STREAM_EDIT_INTERVAL:
                    block_start = current_block * DISCORD_MAX_MESSAGE_LENGTH
                    block_text = full_text[
                        block_start : block_start + DISCORD_MAX_MESSAGE_LENGTH
                    ]
                    await current_message.edit(content=block_text)
                    last_edit_time = now
        except Exception:
            # If streaming failed mid-way, fall through to send whatever we have
            logger.error("Error during chat", exc_info=True)

        # Final edit with the complete text for the last block
        logger.debug(
            "Stream complete, total length=%d, blocks=%d",
            len(full_text),
            current_block + 1,
        )
        if full_text:
            block_start = current_block * DISCORD_MAX_MESSAGE_LENGTH
            block_text = full_text[
                block_start : block_start + DISCORD_MAX_MESSAGE_LENGTH
            ]
            if block_text:
                await current_message.edit(content=block_text)
            else:
                # Empty block (stream ended exactly at a boundary) — delete it
                logger.debug(
                    "Empty trailing block at boundary (total=%d, block=%d), deleting message",
                    len(full_text),
                    current_block,
                )
                try:
                    await current_message.delete()
                except discord.HTTPException:
                    pass
        else:
            await current_message.edit(content="ERROR: OpenAI API call failed.")
