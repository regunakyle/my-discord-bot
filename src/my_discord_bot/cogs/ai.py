import logging
import math
import os

import discord
import openai
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ._cog_base import CogBase, check_cooldown_factory

logger = logging.getLogger(__name__)

# TODO: Handle bad connections


class AI(CogBase):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ) -> None:
        super().__init__(bot, sessionmaker)
        self.client = openai.OpenAI()
        self.model_name = os.getenv("OPENAI_MODEL_NAME", "")

    @discord.app_commands.command()
    @discord.app_commands.checks.dynamic_cooldown(check_cooldown_factory(15))
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(
        message="Message to the AI.",
        prompt="Prompt for the AI. Default prompt is focused on answering programming questions.",
        temperature="(Default: 100) Value between 0 and 200. Lower value makes the AI more focused and deterministic.",
    )
    async def chat(
        self,
        ia: discord.Interaction,
        message: str,
        prompt: str = "You are an experienced full-stack programmer. You excel in Java, Javascript and Python. You enjoy answering programming questions with code and provide concise explanations.",
        temperature: int = 100,
    ) -> None:
        """(RATE LIMITED) Chat with AI."""
        # TODO: Stream the message instead, edit the Discord response as new chunks arrive

        await ia.response.defer()

        message = (
            self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
                    },
                    {
                        "role": "user",
                        "content": message,
                    },
                ],
                temperature=temperature / 100,
                max_tokens=2000,
            )
            .choices[0]
            .message.content
        )

        await ia.followup.send(message[:2000])

        if len(message) > 2000:
            for split in range(1, math.ceil(len(message) / 2000) + 1):
                await ia.followup.send(message[2000 * split : 2000 * (split + 1)])

    @discord.app_commands.command()
    @discord.app_commands.describe(
        model_name="(OWNER ONLY) Set the name of the model used by the /chat command.",
    )
    async def chat_model(
        self, ia: discord.Interaction, model_name: str | None = None
    ) -> None:
        """Print the model name used by the /chat command."""
        if not model_name:
            await ia.response.send_message(
                f"Current model used by /chat: `{self.model_name}`."
            )
            return

        if not await self.bot.is_owner(ia.user):
            await ia.response.send_message("Only the bot owner may change the model!")
            return

        self.model_name = model_name
        await ia.response.send_message(f"LLM model changed to `{model_name}`.")
