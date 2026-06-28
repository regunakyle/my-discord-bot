import typing as ty

from sqlalchemy import ForeignKey, Identity, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ._model_base import ModelBase

if ty.TYPE_CHECKING:
    from .guild import Guild


class Translation(ModelBase):
    __tablename__ = "translation"

    id: Mapped[int] = mapped_column(
        Identity(always=True, start=1, increment=1), primary_key=True
    )
    guild_id: Mapped[int] = mapped_column(
        ForeignKey("guild.id", ondelete="CASCADE"), unique=True
    )
    trigger_emote: Mapped[str] = mapped_column(Unicode(50))
    english_channel_id: Mapped[int] = mapped_column()

    guild: Mapped["Guild"] = relationship(
        back_populates="translation",
        lazy="raise",
    )
