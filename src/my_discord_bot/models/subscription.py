import datetime as dt
import typing as ty

from sqlalchemy import Identity, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ._model_base import ModelBase

if ty.TYPE_CHECKING:
    from .guild import Guild
    from .subscription_announcement import SubscriptionAnnouncement


class Subscription(ModelBase):
    __tablename__ = "subscription"

    id: Mapped[int] = mapped_column(
        Identity(always=True, start=1, increment=1), primary_key=True, init=False
    )
    guild_id: Mapped[int] = mapped_column()
    youtube_channel_id: Mapped[str] = mapped_column(String(50), unique=True)
    youtube_upload_playlist: Mapped[str] = mapped_column(String(50))
    last_checked_at: Mapped[dt.datetime] = mapped_column(
        default=dt.datetime.now(dt.UTC)
    )

    guild: Mapped["Guild"] = relationship(
        back_populates="subscriptions",
        lazy="raise",
    )
    announcements: Mapped[ty.List["SubscriptionAnnouncement"]] = relationship(
        back_populates="subscription",
        lazy="raise",
        cascade="save-update, merge, delete",
    )
