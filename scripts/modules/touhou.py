from discord.ext import commands

# TODO: 5 task(s)
# Get into touhou guide
# Subscription to certain people, e.g. ZUN
# Ask trivia question; Validate answer
# Set/Remove trivia
# Character search function, use elasticsearch


class Touhou(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
