from discord.ext import commands
from ..utility import utility as util
import subprocess, re, discord, os, typing as ty, yfinance as yf, logging

logger = logging.getLogger(__name__)


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def forex(
        self,
        ctx: commands.Context,
        amount: str,
        start_currency: str,
        target_currency: str,
    ) -> None:
        """Convert currency.
        Example: >>forex 100 HKD USD"""
        forex = (
            f"{start_currency}{target_currency}=X"
            if start_currency.lower() != "usd"
            else target_currency + "=X"
        )
        try:
            assert 0 <= float(amount) < 1e10
            newAmt = round(
                yf.Ticker(forex).history("1d").iloc[0]["Close"] * float(amount), 2
            )
            await ctx.send(
                f"{amount} {start_currency} = {str(newAmt)} {target_currency}",
                reference=ctx.message,
            )
        except Exception as e:
            logger.error(e)
            await ctx.send(
                "Something went wrong. Most likely you inputted nonexistent currency code(s).",
                reference=ctx.message,
            )

    @commands.command()
    async def p(
        self, ctx: commands.Context, pixiv_link: str, is_webm: ty.Optional[str] = None
    ):
        """Show the first picture (or video) of ***pixiv_link***.
        Input anything after ***pixiv_link*** if your image is animated"""
        link = (
            re.compile(r"(www\.pixiv\.net\/(?:en\/)?artworks\/[0-9]+)")
            .search(pixiv_link)
            .group()
        )
        command = ["gallery-dl", link, "--range", "1"]
        if is_webm:
            command.append("--ugoira-conv")
        result = subprocess.run(command, capture_output=True, text=True)
        if len(result.stdout) == 0:
            await ctx.send(
                "Something went wrong. Maybe your link is invalid?",
                reference=ctx.message,
            )
        else:
            link = os.path.join(
                os.getcwd(),
                "volume",
                "gallery-dl",
                re.compile(r"pixiv.*").search(result.stdout).group(),
            )
            if (
                ctx.guild.premium_subscription_count < 7
                and os.path.getsize(link) >= 1000 * 1000 * 8
            ):  # Server level 1 or below, file size 8MB maximum
                await ctx.send("The image/video is too big!", reference=ctx.message)
            elif (
                ctx.guild.premium_subscription_count < 14
                and os.path.getsize(link) >= 1000 * 1000 * 50
            ):  # Server level 2, file size 50MB maximum
                await ctx.send("The image/video is too big!", reference=ctx.message)
            elif os.path.getsize(link) >= 1000 * 1000 * 100:
                # Server level 3, file size 100MB maximum
                await ctx.send("The image/video is too big!", reference=ctx.message)
            else:
                await ctx.send(file=discord.File(link), reference=ctx.message)
                os.remove(link)


# TODO: 2 Task(s)
# Poll Creator
# xkcd feedparser
