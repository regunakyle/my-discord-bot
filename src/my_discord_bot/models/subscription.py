import datetime as dt
import typing as ty

from sqlalchemy import ForeignKey, Identity, String, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ._model_base import ModelBase

if ty.TYPE_CHECKING:
    from .guild import Guild


class Subscription(ModelBase):
    __tablename__ = "subscription"

    id: Mapped[int] = mapped_column(
        Identity(always=True, start=1, increment=1), primary_key=True
    )
    guild_id: Mapped[int] = mapped_column(
        ForeignKey(
            "guild.id",
            ondelete="CASCADE",
        )
    )
    youtube_channel_name: Mapped[str] = mapped_column(Unicode(50))
    youtube_channel_id: Mapped[int] = mapped_column(unique=True)
    youtube_upload_playlist: Mapped[str] = mapped_column(String(50))
    announcement_target: Mapped[None | str] = mapped_column(String(50), default=None)
    last_checked_at: Mapped[dt.datetime] = mapped_column(
        default=lambda: dt.datetime.now(dt.UTC)
    )

    guild: Mapped["Guild"] = relationship(
        back_populates="subscriptions",
        lazy="raise",
    )
