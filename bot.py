import discord
import stock
import steam
import random

class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))

    async def on_message(self, message):
        print('Message from {0.author}: {0.content}'.format(message))

        #Prevent self loop
        if message.author == self.user:
            return

        if message.content.startswith('!hello'):
            await message.channel.send('Hello World!')

