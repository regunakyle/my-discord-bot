import datetime as dt
import typing as ty

from sqlalchemy import Identity, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ._model_base import ModelBase

if ty.TYPE_CHECKING:
    from .subscription import Subscription


class SubscriptionAnnouncement(ModelBase):
    __tablename__ = "subscription_announcement"

    id: Mapped[int] = mapped_column(
        Identity(always=True, start=1, increment=1), primary_key=True, init=False
    )
    subscription_id: Mapped[int] = mapped_column()
    youtube_video_id: Mapped[str] = mapped_column(String(50), unique=True)
    youtube_upload_playlist: Mapped[str] = mapped_column(String(50))
    last_checked_at: Mapped[dt.datetime] = mapped_column(
        default=dt.datetime.now(dt.UTC)
    )

    subscription: Mapped["Subscription"] = relationship(back_populates="announcements")
