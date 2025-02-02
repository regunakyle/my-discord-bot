from sqlalchemy import Identity, String
from sqlalchemy.orm import Mapped, mapped_column

from ._model_base import ModelBase


class Guild(ModelBase):
    __tablename__ = "guild"

    id: Mapped[int] = mapped_column(
        Identity(always=True, start=1, increment=1), primary_key=True
    )
    guild_id: Mapped[int] = mapped_column(unique=True)
    guild_name: Mapped[str] = mapped_column(String(100))
    bot_channel: Mapped[None | int] = mapped_column()
    welcome_message: Mapped[None | str] = mapped_column(String(2000))
