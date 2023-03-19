import typing as ty
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from .model_base import ModelBase


class GuildInfo(ModelBase):
    __tablename__ = "guild_info"

    id: Mapped[UUID] = mapped_column(init=False, primary_key=True, default=uuid4)
    guild_id: Mapped[int] = mapped_column(unique=True)
    guild_name: Mapped[str] = mapped_column(String(100))
    bot_channel: Mapped[ty.Optional[int]] = mapped_column(default=None)
    welcome_message: Mapped[ty.Optional[str]] = mapped_column(
        String(2000), default=None
    )
    last_updated: Mapped[datetime] = mapped_column(
        insert_default=datetime.utcnow(), default=None
    )
