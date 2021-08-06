import discord
from discord.ext import commands
from ..utility import utility as util

#Reference: https://gist.github.com/InterStella0/b78488fb28cadf279dfd3164b9f0cf96
class MyHelpCommand(commands.MinimalHelpCommand):
    def get_command_signature(self, command):
        return '%s%s %s' % (self.clean_prefix, command.qualified_name, command.signature)

    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="Help")
        for cog, commands in mapping.items():
           filtered = await self.filter_commands(commands, sort=True)
           command_signatures = [self.get_command_signature(c) for c in filtered]
           if command_signatures:
                cog_name = getattr(cog, "qualified_name", "No Category")
                embed.add_field(name=cog_name, value="\n".join(command_signatures), inline=False)

        channel = self.get_destination()
        await channel.send(embed=embed)

class Meta(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = MyHelpCommand()
        bot.help_command.cog = self
    
    def cog_unload(self):
        self.bot.help_command = self._original_help_command
    
    @commands.command()
    async def setBotChannel(self,ctx,unset=None):
        """Set the channel for bot notifications."""
        try: 
            util.runSQL("INSERT OR REPLACE INTO guildInfo values (?,?,?,Datetime())",(ctx.guild.id,ctx.guild.name,ctx.channel.id if unset is None else None))
            await ctx.channel.send("Update complete.",reference=ctx.message)   
        except Exception as e:
            util.print(e)
            await ctx.send("Operation failed. Something went wrong.",reference=ctx.message) 

#TODO: 1 Task(s)
# Custom help command