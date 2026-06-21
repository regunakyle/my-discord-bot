import logging
import os
import typing as ty
from collections.abc import Iterable

import discord
import openai
from discord.ext import commands
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


def check_cooldown_factory(
    seconds: float = 10,
) -> ty.Callable[[discord.Interaction], discord.app_commands.Cooldown | None]:
    """Global cooldown for commands."""

    def check_cooldown(
        ia: discord.Interaction,
    ) -> discord.app_commands.Cooldown | None:
        if ia.user.id == ia.client.application.owner.id:
            return None
        return discord.app_commands.Cooldown(1, seconds)

    return check_cooldown


class CogBase(commands.Cog):
    def __init__(
        self, bot: commands.Bot, sessionmaker: async_sessionmaker[AsyncSession]
    ) -> None:
        self.bot = bot
        self.sessionmaker = sessionmaker

        self.model_name = os.getenv("OPENAI_MODEL_NAME", "")
        self.client = openai.AsyncOpenAI()

    def get_max_file_size(
        self,
        guild: None | discord.Guild,
    ) -> int:
        """Return the maximum file size (in MiB) supported by the current guild.

        If MAX_FILE_SIZE in .env is smaller than this size, return MAX_FILE_SIZE instead.
        """

        if guild is None:
            return 10

        # Nitro level and their maximum upload size
        nitroCount = guild.premium_subscription_count
        maxSize = 100  # Level 3
        if nitroCount < 7:  # Level 1 or lower
            maxSize = 25
        elif nitroCount < 14:  # Level 2
            maxSize = 50

        try:
            return min(maxSize, abs(int(os.getenv("MAX_FILE_SIZE", "25"))))
        except Exception:
            return maxSize

    async def call_openai_stream(
        self,
        messages: Iterable[ChatCompletionMessageParam],
    ) -> ty.AsyncGenerator[str, None]:
        """Stream an OpenAI chat completion. Yields each text chunk as it arrives."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                stream=True,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error("OpenAI API stream failed:", e)
