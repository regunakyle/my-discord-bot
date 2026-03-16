from .ai import AI
from .error_handler import ErrorHandler
from .general import General
from .meta import Meta
from .music import Music
from .subscription import Subscription

cog_list = [
    ErrorHandler,
    General,
    Meta,
    AI,
    Subscription,
    Music,
]

__all__ = (
    "ErrorHandler",
    "General",
    "Meta",
    "AI",
    "cog_list",
    "Subscription",
    "Music",
)
