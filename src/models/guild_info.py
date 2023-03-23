import typing as ty
from uuid import UUID, uuid4

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .model_base import ModelBase


class GuildInfo(ModelBase):
    __tablename__ = "guild_info"

    # Columns
    id: Mapped[UUID] = mapped_column(init=False, primary_key=True, default=uuid4)
    guild_id: Mapped[int] = mapped_column(unique=True)
    guild_name: Mapped[str] = mapped_column(String(100))
    bot_channel: Mapped[ty.Optional[int]] = mapped_column(default=None)
    welcome_message: Mapped[ty.Optional[str]] = mapped_column(
        String(2000), default=None
    )

    # Relationships
    guild_tasks: Mapped[ty.List["GuildTask"]] = relationship(
        back_populates="guild_info",
        init=False,
        lazy="raise",
    )
