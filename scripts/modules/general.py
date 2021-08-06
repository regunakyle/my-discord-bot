from discord.ext import commands
from PIL import Image
import yfinance as yf
from ..utility import utility as util
import subprocess,re,discord,os
import requests

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def forex(self,ctx,amt,start,target):
        """Convert currency."""
        forex = start + target + "=X" if start.lower() != 'usd' else target + "=X"
        try:
            newAmt = round(yf.Ticker(forex).history("1d").iloc[0]['Close'] * float(amt),2)
            await ctx.send(amt+start+" = " + str(newAmt)+target,reference=ctx.message)
        except Exception as e:
            util.print(e)
            await ctx.send("Something went wrong. Most likely you inputted nonexistent currency code(s).",reference=ctx.message)
        
    @commands.command()
    async def p(self,ctx,plink,webm = None):
        """Show the first picture (or video) of Pixiv link."""
        link = re.compile(r"(www\.pixiv\.net\/(?:en\/)?artworks\/[0-9]+)").search(plink).group()
        command = ['gallery-dl',link,"--range","1"]
        if webm:
            command.append("--ugoira-conv-lossless")
        result = subprocess.run(command, capture_output=True, text=True)
        if len(result.stdout) == 0:
            await ctx.send("Something went wrong. Maybe your link is invalid?",reference=ctx.message)
        else:
            link = re.compile(r"(\.\\gallery-dl\\pixiv\\.+)").search(result.stdout).group()
            if os.path.getsize(link) >= 8000000:
                await ctx.send("The image/video is too big!",reference=ctx.message)
            else:
                await ctx.send(file=discord.File(link),reference=ctx.message)
                #This works!
                os.remove(link) 
    
    @commands.command()
    async def t(self,ctx,tlink):
        """Show video/gif of twitter link."""

#TODO: 6 Task(s)
#Twitter animation downloader
#燦神Calculator 
#Poll Creator
#xkcd feedparser
#Bonus: Chatbot AI