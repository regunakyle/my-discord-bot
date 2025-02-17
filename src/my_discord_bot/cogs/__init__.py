from .ai import AI
from .error_handler import ErrorHandler
from .general import General
from .meta import Meta
from .music import Music

cog_list = [ErrorHandler, General, Meta, Music, AI]

__all__ = ("ErrorHandler", "General", "Meta", "Music", "AI", "cog_list")
