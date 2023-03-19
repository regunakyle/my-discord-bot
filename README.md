# Reguna's Discord Bot

Written in Python 3.11 using [discord.py](https://github.com/Rapptz/discord.py).

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
      MAX_FILE_SIZE: ${MAX_FILE_SIZE}
      PREFIX: ${PREFIX}
      DATABASE_CONNECTION_STRING: ${DATABASE_CONNECTION_STRING}
      LOGGER_LEVEL: ${LOGGER_LEVEL}
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
3. ChatGPT support
4. Fun bot commands that might interest you (e.g. Currency convertion, Posting raw Pixiv images)

## TODO List

- [ ] Music.play: Add Spotify support
- [ ] Bot commands:
  - [ ] Music.loop
- [ ] Support for other databases
- [ ] Use alembic to make database migration scripts
- [ ] Create a dashboard for the bot

## Notable commands

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

### `/connect_node`

- Connect to a new node from the Lavalink server.

  Use this command if you experience problems with the music player.

  Note: Do not use this command while the bot is playing music!
