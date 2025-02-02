# Reguna's Discord Bot

Written in Python using [discord.py](https://github.com/Rapptz/discord.py).

Data are stored in an embedded SQLite3 database file.

## Deployment guide

This Discord bot is developed with Python 3.11. Use the same Python version to ensure maximum compatibility.

1. Download the whole source code using `git clone`.

2. Rename `.env.example` to `.env` and put your Discord token inside.

3. Create a virtual python environment, activate it, then install dependencies with `pip install -e .`.

4. Run `python -m my_discord_bot` in your console to start up the bot.

5. To use the music player, you need to run a [Lavalink](https://github.com/freyacodes/Lavalink) instance alongside the bot. Set `LAVALINK_URL` and `LAVALINK_PASSWORD` in `.env`.

    Example config file (`application.yml`) for Lavalink:

```yaml
server:
  port: 2333
  address: 0.0.0.0
plugins:
  youtube:
    enabled: true
    clients: ["MUSIC", "WEB", "MWEB", "WEBEMBEDDED", "ANDROID_MUSIC", "ANDROID_VR", "TV", "TVHTML5EMBEDDED"]
    oauth:
    # See https://github.com/lavalink-devs/youtube-source?tab=readme-ov-file#using-oauth-tokens for more info
      enabled: true
      refreshToken: <Use your own oauth token here>
lavalink:
  plugins:
  # See https://github.com/lavalink-devs/youtube-source for the latest version of the plugin
    - dependency: "dev.lavalink.youtube:youtube-plugin:1.11.4"
  server:
    password: "youshallnotpass"
    sources:
      youtube: false
```

6. To use the AI chat command, set `OPENAI_API_KEY` and `OPENAI_MODEL_NAME` in `.env`.

## Docker Compose

If you prefer Docker, you can use the Docker Compose file [here](compose.yaml).

Note: The `latest` tag refers to the latest stable version.

## Features

1. A music player to play Youtube videos in any voice channel (requires a Lavalink server)
2. Chat with AI (requires an OpenAI compatible API server, e.g. [tabbyAPI](https://github.com/theroyallab/tabbyAPI))
3. A bunch of other commands I created for my needs...

## TODO List

- [ ] Bot commands:
  - [ ] Music.play: Add Spotify support
  - [ ] General.pixiv: Rewrite (refer to Phixiv implementation)
  - [ ] AI.draw: Add [stable-diffusion-webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui) support
- [ ] Allow passing arguments to FFMPEG (for hardware acceleration)
- [ ] Allow bot owner to run every command (including admin only commands)

## Notable commands

**Please use `/help` to see the full list of commands!**

The list below only shows a subset of commands which I think need further explanation.

(Parameters in `[square brackets]` are mandatory; Those in `<angled brackets>` are optional)

### `>>sync`

- Reload application commands (i.e. slash commands) and syncing database.

  Only the owner of the bot may use this command.

  **Please run this command once after first install and after every update!**

  Note: Replace `>>` with the `PREFIX` you set in `.env` (or `compose.yaml` if you are using Docker)

### `/help <command_name>`

- Display all available commands
  - `<command_name>`: Display the information of the command

### `/pixiv [pixiv_link] <image_number> <animation_format>`

- Post the `<image_number>`th picture (or video) of `[pixiv_link]`.
  - `[pixiv_link]`: Pixiv image link
  - `<image_number>`: Image number (for albums with multiple images); 1 by default
  - `<animation_format>`: `webm` or `gif`. GIF can loop, but might fail to deliver due to much larger size; `webm` by default

     **`gif` will have bad quality if the bot is not run in Linux!**

#### **Important**: You must have `ffmepg` installed and setup an OAuth token to use this command

  To set the OAuth token, run `gallery-dl oauth:pixiv`, then follow the instructions given.

- **If you are using Docker**, `ffmpeg` has already been installed for you.

    Start the discord bot container, then run in console:

    1. `docker exec -it <container-name-or-id> /bin/bash`
    2. `gallery-dl oauth:pixiv`
    3. Follow the instructions given

### `/connect_music`

- Establish a new connection to the Lavalink server.

  Use this command if the music player is not working while the Lavalink server is up.

  Do NOT use this command while the bot is playing music!

- Lavalink can be unstable (probably because YouTube changes their Innertube API often).

  If the music player consistently produce errors, go to the Lavalink discord to check if there is a hotfix version of Lavalink.

### `/chat_model <model_name>`

- Print the model name used by the `/chat` command.

  If `model_name` is set, change the model used by the `/chat` command. (only the bot owner can do this!)
