import datetime as dt
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ._model_base import ModelBase


class SteamBlacklist(ModelBase):
    __tablename__ = "steam_blacklist"

    id: Mapped[UUID] = mapped_column(init=False, primary_key=True, default=uuid4)
    guild_id: Mapped[int] = mapped_column(
        ForeignKey("guild_info.guild_id", onupdate="CASCADE", ondelete="CASCADE")
    )
    keyword: Mapped[str] = mapped_column(String(253))
    time_added: Mapped[dt.datetime] = mapped_column(
        insert_default=dt.datetime.utcnow(), default=None
    )
