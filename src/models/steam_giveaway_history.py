import datetime as dt

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models._model_base import ModelBase


class SteamGiveawayHistory(ModelBase):
    __tablename__ = "steam_giveaway_history"

    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100))
    link: Mapped[str] = mapped_column(String(300))
    publish_time: Mapped[dt.datetime]
    expiry_date: Mapped[None | dt.datetime] = mapped_column(Date, default=None)
