# Reguna's Discord Bot

Written in Python using [discord.py](https://github.com/Rapptz/discord.py).

Data are stored in an embedded SQLite3 database file.

## Deployment guide

1. Download the whole source code using `git clone`.

2. Rename `.env.example` to `.env` and put your Discord token inside.

3. Create a virtual python environment and install dependencies from `requirements.txt`.

4. Run `python main.py` in your console to start up the bot.

5. To use the music player, you need to run a [Lavalink](https://github.com/freyacodes/Lavalink) instance alongside the bot.

   The config for Lavalink can be found in `.env`.

## Docker Compose

If you prefer Docker, you can use the docker compose file [here](docker-compose.yaml).

## Features

1. Notify you when there are free game giveaways
2. A music player to play Youtube videos in any voice channel
3. A bunch of other commands I created for my needs...

## TODO List

- [ ] Bot commands:
  - [ ] General.chat
  - [ ] Music.play: Add Spotify support
- [ ] Support for MySQL/MariaDB and PostgreSQL

## Notable commands

Parameters in `[square brackets]` are mandatory; Those in `<angled brackets>` are optional.

### `>>sync`

- Reload application commands (i.e. slash commands).

  Only the owner of the bot may use this command.

  **Please run this command once after first install and after every update!**

  Note: Replace `>>` with the `PREFIX` you set in `.env` (or `docker-compose.yaml` if you are using Docker)

### `/help <command_name>`

- Display all available commands
  - `<command_name>`: Display the information of the command

### `/set_bot_channel`

- Mark the current channel as the subscription channel.

  All subscription messages will be sent in that channel.

  (Currently only Steam free giveaway notification is available)

### `/set_welcome_message <message>`

- Set the welcome message sent to the system channel when a new member joins the current server.

  - `<message>`: You can use `\n`, `<#ChannelNumber>`, `<@UserID>`, `<a:EmojiName:EmojiID>`.

    If empty, unset the welcome message

### `/pixiv [pixiv_link] <image_number>`

- Post the `<image_number>`th picture (or video) of `[pixiv_link]`.
  - `[pixiv_link]`: Pixiv image link
  - `<image_number>`: Image number (for albums with multiple images), by default 1
- **Important**: To use this command, first install `ffmepg`,

  then run (in your python environment): `gallery-dl oauth:pixiv`, and follow the instructions given.

  - If you are using Docker, `ffmpeg` has already been installed for you.

    Start the discord bot container, then run in console:

    1. `docker exec -it <container-name-or-id> /bin/bash`
    2. `gallery-dl oauth:pixiv -o browser=`
    3. Follow the instructions given

### `/connect_music`

- Establish a new connection to the Lavalink server.

  Use this command if the music player is not working while the Lavalink server is up.

  Note: Do not use this command while the bot is playing music!
