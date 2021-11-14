# Reguna's Discord Bot

Written in Python3.9 using [Pycord](https://github.com/Pycord-Development/pycord).

Data are stored in an embedded sqlite3 database file.

## Deployment guide

1. Create a _.env_ file and add this line to it:
   <!-- prettier-ignore -->
      - DISCORD_TOKEN=**_YOUR DISCORD TOKEN_**

2. (Recommended) Create a virtual python environment and install dependencies from _requirements.txt_.

3. Run _python main&#46;py_ in your console.

## Docker

If you prefer Docker, a recommended way is to run **(after creating _.env_ with _DISCORD_TOKEN_)**:

- _docker compose up -d_

or you can pull the image from [here](https://hub.docker.com/r/regunakyle/discordbot) and run:

- _docker run -env DISCORD_TOKEN=**YOUR DISCORD TOKEN** -d regunakyle/discordbot:0.1.1_

## Features

1. Notify you when there are new game deals
2. Search for new game deals every 2 hours
3. Also other bot commands...

## List of bot commands (command prefix: >>)

Note: Parameters in _\[square brackets\]_ are mandatory,

while those in _\<angle brackets\>_ are optional.

### >>help _\<command>_

- Display all available commands
  - With _**command**_: display information of the command

### >>setBotChannel _\<-unset>_

- Set the channel as the bot channel: all automated messages will be sent in bot channel.
- With _**-unset**_: remove previously set bot channel
- **Important**: Game deal notifications are disabled if there is no designated bot channel

### >>blacklist _\<domain\>_ _\<\-r\>_

- Print out current blacklisted domains
- With _**domain**_: insert _domain_ into blacklist, ignoring future game deals from _domain_
- With _**domain**_ and _**-r**_ : remove _domain_ from blacklist

### >>getAllRecord

- Get all previous game deals from database (in _.csv_ format)

### >>forex _\[amount\]_ _\[starting currency\]_ _\[target currency\]_

- Convert currency. Using data from Yahoo Finance
  - Example: >>forex 10000 HKD USD
    - Convert 10000 HKD to USD

### >>p _\[pixiv url\]_ _\<-webm>_

- Get the full image from _**pixiv url**_
  - Add _**-webm**_ if your image is animated
- **Important**: To use this feature, first install _ffmepg_ in your system, then run in console (in your python environment): _gallery-dl oauth:pixiv_
  - If you are using Docker, _ffmpeg_ has already been installed for you. Start the discord bot container, then run in console:
    - _docker exec -it \<container-name-or-id\> /bin/bash_
    - Then run _gallery-dl oauth:pixiv_ in the newly spawned bash shell.
