import datetime as dt

from sqlalchemy import ForeignKey, String
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models._model_base import ModelBase
from src.models.guild import Guild


class GuildTask(ModelBase):
    __tablename__ = "guild_task"

    # Columns
    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(
        ForeignKey("guild.guild_id", onupdate="CASCADE", ondelete="CASCADE")
    )
    task_name: Mapped[str] = mapped_column(String(100))
    last_run: Mapped[dt.datetime] = mapped_column(
        insert_default=dt.datetime.utcnow(), default=None
    )

    # Relationships
    guild: Mapped[Guild] = relationship(
        init=False,
        lazy="noload",
    )
    bot_channel: AssociationProxy[int] = association_proxy(
        "guild", "bot_channel", init=False
    )
