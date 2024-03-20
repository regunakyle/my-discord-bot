from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.models._model_base import ModelBase


class Guild(ModelBase):
    __tablename__ = "guild"

    id: Mapped[int] = mapped_column(init=False, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(unique=True)
    guild_name: Mapped[str] = mapped_column(String(100))
    bot_channel: Mapped[None | int] = mapped_column(default=None)
    welcome_message: Mapped[None | str] = mapped_column(String(2000), default=None)
