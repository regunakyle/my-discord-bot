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

    async def call_openai(
        self,
        messages: Iterable[ChatCompletionMessageParam],
    ) -> str | None:
        """Make a generic OpenAI API call. Returns the assistant's text, or None on failure."""

        api_key = os.getenv("OPENAI_API_KEY", "")
        model_name = os.getenv("OPENAI_MODEL_NAME", "")
        base_url = os.getenv("OPENAI_BASE_URL")

        if not api_key or not model_name:
            logger.warning("OpenAI API key or model name not configured.")
            return None

        try:
            client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=None if not base_url else base_url,
            )
            response = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("OpenAI API call failed:", exc_info=e)
            return None
