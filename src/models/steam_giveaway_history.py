import typing as ty
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .model_base import ModelBase


class SteamGiveawayHistory(ModelBase):
    __tablename__ = "steam_giveaway_history"

    id: Mapped[UUID] = mapped_column(init=False, primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(100))
    link: Mapped[str] = mapped_column(String(300))
    publish_time: Mapped[datetime]
    expiry_time: Mapped[ty.Optional[datetime]] = mapped_column(DateTime, default=None)
