# Reguna's Discord Bot

Written in Python 3.10 using [discord.py](https://github.com/Rapptz/discord.py).

Data are stored in an embedded sqlite3 database file.

## Deployment guide

1. Download the whole source code using `git clone`.

2. Rename `.env.example` to `.env` and put your Discord token inside.

3. Create a virtual python environment and install dependencies from `requirements.txt`.

4. Run `python main.py` in your console to start up the bot.

5. To use the music player, you should download [Lavalink](https://github.com/freyacodes/Lavalink) and run it alongside the Discord bot.

   The config for Lavalink can also be found in `.env`.

## Docker Compose

If you prefer Docker, you can use the following Docker Compose.

Please refer to [this guide](https://docs.docker.com/compose/environment-variables/) for how to set the necessary environment variables.

```yaml
---
version: "3.9"

services:
  discordbot:
    container_name: discordbot
    image: regunakyle/discordbot
    environment:
      DISCORD_TOKEN: ${DISCORD_TOKEN}
      LAVALINK_IP: ${LAVALINK_IP}
      LAVALINK_PORT: ${LAVALINK_PORT}
      LAVALINK_PASSWORD: ${LAVALINK_PASSWORD}
      PREFIX: ">>"
    volumes:
      - dbot-vol:/app/volume
    restart: unless-stopped
  lavalink:
    container_name: lavalink
    image: fredboat/lavalink
    environment:
      server.port: ${LAVALINK_PORT}
      lavalink.server.password: ${LAVALINK_PASSWORD}
    ports:
      - ${LAVALINK_PORT}:${LAVALINK_PORT}
    restart: unless-stopped

volumes:
  dbot-vol:
    name: dbot-vol

networks:
  default:
    name: discord-bot-network
```

I suggest you use [Adminer](https://hub.docker.com/_/adminer) or [CloudBeaver](https://hub.docker.com/r/dbeaver/cloudbeaver) alongside the bot for easier database management.

## Features

1. Notify you when there are new game giveaways
2. Search for new game giveaways every 2 hours
3. Also other bot commands (including a music player)...

## TODO List

- [ ] Dynamic welcome message
- [ ] Subscription to tweets
- [ ] Music bot commands:
  - [ ] Loop
  - [ ] Move

## List of bot commands (Not updated)

Parameters in `[square brackets]` are mandatory,

while those in `<angle brackets>` are optional.

Default prefix for old style prefix command is `>>` (Can be changed in `.env` or `docker-compose.yaml`).

### `{prefix}sync <option>`

- Reload application commands (i.e. slash commands).

  Only the owner of the bot may use this command.

  **Please run this command once after first install and after every update!**

  - `<option>`: For development purpose only, please refer to the source code :)

### `/help <command_name>`

- Display all available commands
  - `<command_name>`: Display the information of the command

### `/setbotchannel <is_unset>`

- Mark the current channel as the subscription channel.

  All notification will be sent here.

  - `<is_unset>`: Set to `True` if you want to unmark the subscription channel

### `/blacklist <target_domain> <is_remove>`

- Blacklist domains for the find giveaway task.

  No notification will be sent for blacklisted domains.

  - `<target_domain>`: Domain of the game site you wish to blacklist

  - `<is_remove>`: Set to `True` if you want to remove `<target_domain>` from blacklist

### `/forex [amount] [starting currency] [target currency]`

- Convert currency using data from Yahoo Finance.
  - `[amount]`: Amount in `[starting_currency]`, ranged from 0 to 1,000,000,000
  - `[starting_currency]`: Starting currency, e.g. `HKD`
  - `[target_currency]`: Target currency, e.g. `JPY`

### `/pixiv [pixiv_link] <image_number>`

- Show the `<image_number>`th picture (or video) of `[pixiv_link]`.
  - `[pixiv_link]`: Pixiv image link
  - `<image_number>`: Image number (for albums with multiple images), by default 1
- **Important**: To use this command, first install `ffmepg`,

  then run (in your python environment): `gallery-dl oauth:pixiv`

  - If you are using Docker, `ffmpeg` has already been installed for you.

    Start the discord bot container, then run in console:

    1. `docker exec -it <container-name-or-id> /bin/bash`
    2. `gallery-dl oauth:pixiv`
