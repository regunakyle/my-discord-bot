import datetime as dt

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models._model_base import ModelBase
from src.models.guild import Guild


class SteamBlacklist(ModelBase):
    __tablename__ = "steam_blacklist"

    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        ForeignKey("guild.guild_id", onupdate="CASCADE", ondelete="CASCADE")
    )
    keyword: Mapped[str] = mapped_column(String(253))
    time_added: Mapped[dt.datetime] = mapped_column(
        insert_default=dt.datetime.utcnow(), default=None
    )

    # Relationships
    guild: Mapped[Guild] = relationship(
        init=False,
        lazy="noload",
    )
