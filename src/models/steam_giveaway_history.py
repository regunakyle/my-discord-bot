import datetime as dt
from uuid import UUID, uuid4

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from ._model_base import ModelBase


class SteamGiveawayHistory(ModelBase):
    __tablename__ = "steam_giveaway_history"

    id: Mapped[UUID] = mapped_column(init=False, primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(100))
    link: Mapped[str] = mapped_column(String(300))
    publish_time: Mapped[dt.datetime]
    expiry_date: Mapped[dt.datetime | None] = mapped_column(Date, default=None)
