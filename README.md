# Reguna's Discord Bot

Written in Python using Pycord.

## Deployment guide

Create a file _app.cfg_ and put it into the _./volume_ folder.

Input the following into _app.cfg_:

---

\[Discord\]

Token=_Your Discord Token_

---

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
