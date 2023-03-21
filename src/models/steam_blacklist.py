import typing as ty
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .model_base import ModelBase


class SteamBlacklist(ModelBase):
    __tablename__ = "steam_blacklist"

    # Columns
    id: Mapped[UUID] = mapped_column(init=False, primary_key=True, default=uuid4)
    guild_id: Mapped[int] = mapped_column(
        ForeignKey("guild_info.guild_id", onupdate="CASCADE", ondelete="CASCADE")
    )
    keyword: Mapped[str] = mapped_column(String(253))
    time_added: Mapped[datetime] = mapped_column(
        insert_default=datetime.utcnow(), default=None
    )

    # Relationships
    guild_info: Mapped["GuildInfo"] = relationship(
        back_populates="steam_blacklists",
        init=False,
        lazy="raise",
    )
