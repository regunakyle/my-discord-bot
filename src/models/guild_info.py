from uuid import UUID, uuid4

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ._model_base import ModelBase


class GuildInfo(ModelBase):
    __tablename__ = "guild_info"

    id: Mapped[UUID] = mapped_column(init=False, primary_key=True, default=uuid4)
    guild_id: Mapped[int] = mapped_column(unique=True)
    guild_name: Mapped[str] = mapped_column(String(100))
    bot_channel: Mapped[int | None] = mapped_column(default=None)
    welcome_message: Mapped[str | None] = mapped_column(String(2000), default=None)
