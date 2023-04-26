# Reguna's Discord Bot

Written in Python using [discord.py](https://github.com/Rapptz/discord.py).

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
    image: regunakyle/my-discord-bot
    environment:
      DISCORD_TOKEN: ${DISCORD_TOKEN}
      # Use "sqlite+aiosqlite:///volume/db.sqlite3" if you are not sure
      DATABASE_CONNECTION_STRING: ${DATABASE_CONNECTION_STRING}
      LOGGER_LEVEL: ${LOGGER_LEVEL}
      # Used by old style prefix commands; this bot only has the <PREFIX>sync prefix command
      PREFIX: ${PREFIX}
      # Maximum file upload size, used by command like /pixiv
      MAX_FILE_SIZE: ${MAX_FILE_SIZE}
      # Lavalink parameters, used by the Music module
      LAVALINK_IP: ${LAVALINK_IP}
      LAVALINK_PORT: ${LAVALINK_PORT}
      LAVALINK_PASSWORD: ${LAVALINK_PASSWORD}
      XDG_CONFIG_HOME: /app/volume
    volumes:
      - dbot-vol:/app/volume
    restart: unless-stopped
  lavalink:
    container_name: lavalink
    image: fredboat/lavalink
    environment:
      server.port: ${LAVALINK_PORT}
      lavalink.server.password: ${LAVALINK_PASSWORD}
    restart: unless-stopped

volumes:
  dbot-vol:
    name: dbot-vol

networks:
  default:
    name: discord-bot-network
```

## Features

1. Notify you when there are free game giveaways
2. A music player to play Youtube video inside a voice channel
3. Fun bot commands that might interest you

## TODO List

- [ ] Bot commands:
  - [ ] Music.loop
  - [ ] Music.play: Add Spotify support
- [ ] AI Chatbot support
- [ ] Support for MySQL/MariaDB and PostgreSQL
- [ ] Use alembic to make database migration scripts
- [ ] Create a dashboard for the bot

## Notable commands

Parameters in `[square brackets]` are mandatory,

while those in `<angle brackets>` are optional.

Default prefix for old style prefix command is `>>` (Can be changed in `.env` or `docker-compose.yaml`).

### `{prefix}sync`

- Reload application commands (i.e. slash commands).

  Only the owner of the bot may use this command.

  **Please run this command once after first install and after every update!**

### `/help <command_name>`

- Display all available commands
  - `<command_name>`: Display the information of the command

### `/set_bot_channel`

- Mark the current channel as the subscription channel.

  All notifications will be sent in that channel.

### `/set_welcome_message <message>`

- Set the welcome message sent to the system channel when a new member joins the server.

  - `<message>`: You can use `\n`, `<#ChannelNumber>`, `<@UserID>`, `<a:EmojiName:EmojiID>`.

    If empty, unset the welcome message

### `/pixiv [pixiv_link] <image_number>`

- Show the `<image_number>`th picture (or video) of `[pixiv_link]`.
  - `[pixiv_link]`: Pixiv image link
  - `<image_number>`: Image number (for albums with multiple images), by default 1
- **Important**: To use this command, first install `ffmepg`,

  then run (in your python environment): `gallery-dl oauth:pixiv`, and follow the instructions given.

  - If you are using Docker, `ffmpeg` has already been installed for you.

    Start the discord bot container, then run in console:

    1. `docker exec -it <container-name-or-id> /bin/bash`
    2. `gallery-dl oauth:pixiv -o browser=`
    3. Follow the instructions given

### `/connect_node`

- Connect to a new node from the Lavalink server.

  Use this command if the music player is not working while the Lavalink server is up.

  Note: Do not use this command while the bot is playing music!
