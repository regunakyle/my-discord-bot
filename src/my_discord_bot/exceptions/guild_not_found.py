import discord


class GuildNotFoundError(Exception):
    """Raised when a command requires the guild to exist in the database but it does not."""

    def __init__(self, guild: discord.Guild) -> None:
        super().__init__(f"Guild {guild.name} ({guild.id}) not found in database.")
