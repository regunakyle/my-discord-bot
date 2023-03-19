import typing as ty
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .model_base import ModelBase


class GuildTask(ModelBase):
    __tablename__ = "guild_task"

    # Columns
    id: Mapped[UUID] = mapped_column(init=False, primary_key=True, default=uuid4)
    guild_id: Mapped[int] = mapped_column(
        ForeignKey("guild_info.guild_id", onupdate="CASCADE", ondelete="CASCADE")
    )
    task_name: Mapped[str] = mapped_column(String(100))
    last_run: Mapped[ty.Optional[datetime]] = mapped_column(default=None)

    # Relationships
    guild_info: Mapped["GuildInfo"] = relationship(
        init=False,
        lazy="raise",
    )
