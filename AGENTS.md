# AGENTS.md — Reguna's Discord Bot

> Reference guide for AI agents implementing new features.

## Project Overview

A personal Discord bot written in **Python 3.13** using **discord.py** with slash commands. Data is persisted in **SQLite3** via **SQLAlchemy (async)** with **Alembic** migrations. The bot is deployable both natively and via **Docker Compose** (with a bundled Lavalink music node).

- **Package name**: `my-discord-bot` (in `src/my_discord_bot/`)
- **Version**: `5.1.0`
- **Build system**: hatchling + `uv` for dependency management
- **License**: GPL-3.0
- **Repository**: `github.com/regunakyle/my-discord-bot`

---

## Directory Layout

```
src/my_discord_bot/
├── __init__.py          # main(), get_bot_version(), entrypoint()
├── bot.py               # DiscordBot class (extends commands.Bot)
├── constants.py         # Shared constants (ACK_EMOJI, TRANSLATION_HEADER_TEMPLATE, etc.)
├── exceptions/          # Custom exceptions
│   ├── __init__.py      # Exports: GuildNotFoundError
│   └── guild_not_found.py
├── cogs/                # Feature modules (see below)
│   ├── __init__.py      # cog_list — registration order matters
│   ├── _cog_base.py     # CogBase mixin + check_cooldown_factory
│   ├── error_handler.py # Global error handler
│   ├── general.py       # /hello, /pixiv
│   ├── meta.py          # >>sync, /help, /set_welcome_message, /version
│   ├── ai.py            # /chat (OpenAI)
│   ├── music.py         # /play, /quit, /queue, /pause, /loop, /skip (Lavalink)
│   ├── subscription.py  # /subscribe + background YouTube live checker
│   └── translation.py   # /translation_setup, /translation_status, /translation_reset + listeners
└── models/              # SQLAlchemy ORM models
    ├── __init__.py      # Exports: ModelBase, Guild, Subscription, Translation
    ├── _model_base.py   # DeclarativeBase with naming conventions
    ├── guild.py         # Guild table
    ├── subscription.py  # Subscription table
    └── translation.py   # Translation table

migrations/              # Alembic migrations (sqlite:///volume/db.sqlite3)
volume/                  # Runtime data (db.sqlite3, logs/, gallery-dl/) — gitignored
assets/images/           # Static images (hello.jpg, error.jpg, music.png)
compose.yaml             # Docker Compose configuration (discordbot + lavalink services)
Dockerfile               # Multi-stage Docker build with uv + ffmpeg
init.sh                  # Docker build helper (downloads ffmpeg, runs uv sync)
```

---

## Architecture

### Entrypoint (`__init__.py`)

1. Loads `.env` via `python-dotenv`
2. Validates `DISCORD_TOKEN` and `PREFIX` are set
3. Creates `volume/logs/` and `volume/gallery-dl/` directories
4. Sets up rotating file logger (`volume/logs/discord.log`, daily, 10 backups)
5. Runs **Alembic migrations** (`command.upgrade(cfg, "head")`)
6. Creates async SQLAlchemy engine against `sqlite+aiosqlite:///volume/db.sqlite3` with `PRAGMA foreign_keys=ON`
7. Instantiates `DiscordBot` and calls `bot.start()`

### Bot Class (`bot.py`)

`DiscordBot(commands.Bot)` — custom bot class:

- **Intents**: `default() + members + message_content`
- **Activity**: `discord.Game(name="/help")`
- **Help command**: Disabled (`self.help_command = None`) — use `/help` instead
- **`setup_hook()`**: Conditionally loads cogs based on env vars (see [Cog Loading](#cog-loading))
- **`on_guild_join()`**: Inserts guild into DB, sends welcome message in system channel
- **`on_guild_remove()`**: Deletes guild from DB
- **`on_member_join()`**: Looks up guild in DB (creates if missing), sends welcome message if configured
- **`on_app_command_completion()`**: Logs all slash command invocations

### Cog Loading

Cogs are registered in `cogs/__init__.py` via `cog_list`. In `setup_hook()`, four cogs are **conditionally loaded**:

| Cog | Required env var(s) |
|---|---|
| `AI` | `OPENAI_API_KEY` AND `OPENAI_MODEL_NAME` (both non-empty) |
| `Music` | `LAVALINK_URL` (non-empty) |
| `Subscription` | `GOOGLE_API_KEY` (non-empty) |
| `Translation` | `OPENAI_API_KEY` AND `OPENAI_MODEL_NAME` (both non-empty) |

`ErrorHandler`, `General`, and `Meta` are **always loaded**.

**To add a new cog**:

1. Create the class in `cogs/your_cog.py` inheriting from `CogBase`
2. Import it and add it to `cog_list` in `cogs/__init__.py`
3. If it needs conditional loading, add a check in `bot.py` `setup_hook()`

### CogBase (`_cog_base.py`)

All cogs inherit from `CogBase(commands.Cog)`:

- Constructor takes `bot: commands.Bot` and `sessionmaker: async_sessionmaker[AsyncSession]`
- Provides `self.bot` and `self.sessionmaker` to all cogs
- Creates `self.client = openai.AsyncOpenAI()` for streaming chat completions
- Stores `self.model_name` from `OPENAI_MODEL_NAME` env var (used by both AI and Translation cogs)
- Stores `self.max_file_size` from `MAX_FILE_SIZE` env var (default `25` MiB)
- `get_max_file_size(guild)` — returns Discord's upload limit capped by `MAX_FILE_SIZE` env var, based on guild Nitro level:
  - Nitro level < 7 (Level 1 or lower): 25 MiB
  - Nitro level < 14 (Level 2): 50 MiB
  - Nitro level >= 14 (Level 3): 100 MiB
  - Returns `10` if `guild` is `None`
- `call_openai_stream(messages)` — async generator that streams OpenAI chat completions via `client.chat.completions.create()`. Uses `extra_body={"chat_template_kwargs": {"enable_thinking": False}}`.
- `check_cooldown_factory(seconds)` — returns a dynamic cooldown check that **exempts the bot owner**

### Database Models

**`Guild`** (`models/guild.py`):

- `id` (auto-increment PK), `guild_id` (unique Discord snowflake), `guild_name` (Unicode(100)), `welcome_message` (nullable, Unicode(2000))
- Relationship: `subscriptions` (one-to-many, `lazy="raise"`, cascade `save-update, merge, delete`)
- Relationship: `translation` (one-to-zero-or-one, `lazy="raise"`, cascade `save-update, merge, delete`)

**`Subscription`** (`models/subscription.py`):

- `id` (auto-increment PK), `guild_id` (FK → guild.id, cascade delete), `youtube_channel_name` (Unicode(100)), `youtube_channel_id` (String(50), composite unique with `guild_id`), `youtube_upload_playlist` (String(50)), `announcement_target` (nullable String(50), role ID), `notification_channel_id` (int, required, per-subscription), `last_checked_at` (datetime, default UTC now)
- Composite unique constraint on `(guild_id, youtube_channel_id)` — allows multiple guilds to subscribe to the same YouTube channel
- Relationship: `guild` (many-to-one, `lazy="raise"`)

**`Translation`** (`models/translation.py`):

- `id` (auto-increment PK), `guild_id` (FK → guild.id, unique, cascade delete), `trigger_emote` (Unicode(50)), `english_channel_id` (int)
- Relationship: `guild` (many-to-one, `lazy="raise"`)

**Adding a new model**:

1. Create file in `models/` inheriting from `ModelBase`
2. Export from `models/__init__.py`
3. Generate migration: `alembic revision --autogenerate -m "description"`
4. Review and commit the migration file

### Global Error Handling (`error_handler.py`)

`ErrorHandler` cog registers `self.bot.tree.on_error = self.on_app_command_error` in its constructor. All error messages are sent as **ephemeral**. It catches:

- `MissingPermissions` → "ERROR: You don't have the required permission!"
- `NoPrivateMessage` → "ERROR: This command is only available inside a server!"
- `CommandOnCooldown` → Shows cooldown message
- `CommandInvokeError` with "error code: 40005" → File too large message with actual max size
- `CommandInvokeError` wrapping `GuildNotFoundError` → Auto-inserts guild into DB, asks user to retry
- All other errors → "ERROR: Something unexpected happened!" + error.jpg

It handles both `ia.response.send_message()` and `ia.followup.send()` (for already-responded interactions).

---

## Cog Details

### General (`general.py`)

| Command | Description |
|---|---|
| `/hello` | Sends `assets/images/hello.jpg` |
| `/pixiv [pixiv_link] <image_number> <animation_format>` | Downloads Pixiv images via `gallery-dl`. 3-second cooldown. Guild-only. |

Key details:

- Uses `gallery-dl` library directly (config + `DownloadJob`)
- Validates URL with regex `(www\.pixiv\.net\/(?:en\/)?artworks\/\d+)`
- Max file size respects guild Nitro level + `MAX_FILE_SIZE` env var
- Defer response (up to 15 min processing time)
- Sends embed with source link + downloaded file
- Error handling by status code:
  - `4` (HttpError): Image too big
  - `8` (NotFoundError): Invalid link
  - `16` (AuthenticationError): No OAuth token configured
  - Other: Generic error

### Meta (`meta.py`)

| Command | Description |
|---|---|
| `>>sync` (hybrid, owner-only) | Re-syncs slash commands globally + syncs guild DB records (deletes stale guilds, inserts current ones) |
| `/help <command_name>` | Lists all commands grouped by cog, or details for a specific command |
| `/set_welcome_message [message]` (admin) | Sets welcome message for new members (max 2000 chars). Supports `\n`, `<#channel>`, `<@user>`, `<a:emoji:id>`. Unescapes `\n` via `unicode-escape` codec. |
| `/version` | Reports bot version (checks `APP_VERSION` env → git branch+hash → pyproject.toml) |

### AI (`ai.py`)

| Command | Description |
|---|---|
| `/chat [message]` | Streams a response from OpenAI-compatible API. 1.5-second cooldown. Guild-only. |

Key details:

- Uses `call_openai_stream()` from `CogBase` (chat.completions streaming API)
- Sends "Thinking..." initially, edits in real-time with 1-second intervals
- Splits across reply messages when exceeding 2000 characters per message
- Falls back to "ERROR: OpenAI API call failed." if no text received
- Sends a single user message `{"role": "user", "content": message}` to the API
- Model name from `OPENAI_MODEL_NAME` env var
- Base URL from `OPENAI_BASE_URL` env var (if empty, uses official OpenAI endpoint; the env var is deleted in `setup_hook` if empty)

### Music (`music.py`)

| Command | Description |
|---|---|
| `/play [query]` | Searches and enqueues a track (YouTube via Lavalink). Handles playlists. |
| `/quit` | Clears queue, stops playback, disconnects from voice |
| `/queue` | Shows current queue (max 20 tracks displayed). Includes currently playing, queue size, paused state, looping state. |
| `/pause` | Toggle pause/resume |
| `/loop` | Toggle single-track loop |
| `/skip` | Skip current track (also cancels loop) |

Key details:

- Uses `lavalink` library (v5.11.0) with custom `LavalinkVoiceClient(discord.VoiceProtocol)`
- `create_player_check` — shared pre-command check that validates voice channel state, permissions, and creates Lavalink player
- Lavalink client stored on `bot.lavalink` (dynamic attribute)
- Background task `leave_inactive_voice_channel_task` (1-min loop): disconnects if no non-bot users in voice channel
- Event hooks: `TrackStartEvent`, `QueueEndEvent`, `TrackLoadFailedEvent`, `NodeReadyEvent`, `NodeDisconnectedEvent`
- Query prefix `ytsearch:` auto-added for non-URL queries
- `/play` handles `LoadType.EMPTY`, `LoadType.PLAYLIST`, and single track enqueuing

### Subscription (`subscription.py`)

| Command | Description |
|---|---|
| `/subscribe [channel_id] [notification_channel] <target_role_id>` (admin) | Subscribe/unsubscribe to YouTube channel for live stream notifications. Notification channel is required and stored per-subscription. |

Key details:

- Uses `googleapiclient.discovery.build("youtube", "v3")` with `GOOGLE_API_KEY`
- Validates bot has `send_messages` permission on the notification channel before subscribing
- Background task `check_subscription` (15-min loop): polls YouTube playlist items (max 50) for new uploads published after `last_checked_at`, filters for scheduled live streams (has `scheduledStartTime` but no `actualStartTime`), posts announcement to the subscription's `notification_channel_id`
- Uses Discord timestamp format `<t:{unix_timestamp}:F>` for scheduled start time
- `last_checked_at` updated to current UTC time after each check
- Announcement pings `target_role_id` or `@everyone` if not specified
- Before loop: waits for bot ready

### Translation (`translation.py`)

| Command | Description |
|---|---|
| `/translation_setup [emote] [english_channel]` (admin) | Configure translation with trigger emote and English channel |
| `/translation_status` | Show current translation configuration |
| `/translation_reset` (admin) | Reset translation configuration |

Key details:

- **Trigger mechanism**: Reacting with the configured `trigger_emote` on a message in a non-English channel translates it to the English channel. Replying to a `[TRANSLATION]` bot message continues the chain.
- **Streaming**: Uses `_stream_translate()` → `call_openai_stream()` from `CogBase`. Sends an initial "Translating..." message and edits in real-time as chunks arrive, splitting across reply messages when exceeding 2000 characters (accounting for header overhead).
- **Header format**: `"[TRANSLATION] {chain_id} | <#{source_channel_id}> | {user_name}"` (8-char hex chain ID + source channel mention + original user name). The ack emoji (`ACK_EMOJI` = ✅) prevents duplicate processing.
- **Direction**: Non-English channel → English (via reaction), English channel reply → Traditional Chinese, source channel reply → English. Direction is determined dynamically based on which channel the reply is in.
- **No file forwarding**: Attachments are not forwarded to the target channel.
- Module-level helpers: `_build_header()`, `_parse_header()`, `_CHANNEL_ID_RE` regex

---

## Constants (`constants.py`)

| Constant | Value | Used By |
|---|---|---|
| `ACK_EMOJI` | `"✅"` | Translation cog (duplicate detection) |
| `TRANSLATION_HEADER_PREFIX` | `"[TRANSLATION] "` | Translation cog (header detection) |
| `TRANSLATION_HEADER_TEMPLATE` | `"[TRANSLATION] {0} | <#{1}> | {2}"` | Translation cog (header formatting) |
| `DISCORD_MAX_MESSAGE_LENGTH` | `2000` | AI + Translation cogs (message splitting) |
| `STREAM_EDIT_INTERVAL` | `1.0` | AI + Translation cogs (edit throttle in seconds) |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | **Yes** | Bot token |
| `PREFIX` | **Yes** | Command prefix (default `>>`); currently only used by `>>sync` |
| `LOG_LEVEL` | No | `DEBUG`, `INFO`, `WARNING`, etc. (default `INFO`) |
| `MAX_FILE_SIZE` | No | Max upload size in MiB (default `25` in code, `.env.example` shows `10`) |
| `LAVALINK_URL` | No* | Lavalink server URL (e.g., `http://localhost:2333`) |
| `LAVALINK_PASSWORD` | No* | Lavalink password (default `youshallnotpass`) |
| `OPENAI_API_KEY` | No* | OpenAI API key (or any string for custom endpoints) |
| `OPENAI_MODEL_NAME` | No* | Model name (default `gpt-3.5-turbo` in `.env.example`) |
| `OPENAI_BASE_URL` | No | Custom OpenAI-compatible endpoint (empty = official) |
| `GOOGLE_API_KEY` | No* | Google API key for YouTube Data API v3 |
| `APP_VERSION` | No | Set during Docker build; overrides version reporting |

\* = Cog is silently not loaded if the required variable(s) are empty.

---

## Key Patterns & Conventions

### Commands

- **All user-facing commands are slash commands** (`@discord.app_commands.command()`), except `>>sync` which is a hybrid command (the only prefix command)
- Commands use `await ia.response.defer()` for long-running operations, then `ia.followup.send()` for the actual response
- Guild-only commands use `@discord.app_commands.guild_only()`
- Admin commands use `@discord.app_commands.checks.has_permissions(manage_channels=True)`
- Rate-limited commands use `@discord.app_commands.checks.dynamic_cooldown(check_cooldown_factory(seconds))`

### Database Access

- Always use `async with self.sessionmaker() as session:` for database sessions
- Use `lazy="raise"` on relationships — you must explicitly `.options(joinedload(...))` when you need related data
- `expire_on_commit=False` is set on the sessionmaker

### Logging

- Use `logging.getLogger(__name__)` in each module
- Logger is configured in `__init__.py` with console + rotating file handler
- All command invocations are logged via `on_app_command_completion`

### Assets

- Images in `assets/images/` are referenced with relative paths from the project root
- `hello.jpg`, `error.jpg`, `music.png`

---

## Deployment

### Native

```bash
cp .env.example .env   # fill in credentials
python -m venv .venv && source .venv/bin/activate
pip install -e .
my-discord-bot          # or: python -m my_discord_bot
```

### Docker

```bash
docker compose up -d
```

The Dockerfile uses a multi-stage build with `uv` for dependency installation and downloads ffmpeg from BtbN builds. The container runs as non-root user (UID 10001).

The `compose.yaml` file defines two services:

- **discordbot**: The bot itself, using `regunakyle/my-discord-bot:latest`
- **lavalink**: Lavalink music node with youtube-source plugin (v1.18.0) using OAuth

Named volume `discord-bot-vol` is mounted at `/app/volume`.

### CI/CD

GitHub Actions (`.github/workflows/docker.yaml`) builds and pushes to Docker Hub on pushes to `master` (tag: `latest`) and `dev` (tag: branch name). `APP_VERSION` is set from pyproject.toml version (master) or git short hash (dev).

### After Updates

Always run `>>sync` in Discord after deploying updates to re-register slash commands and sync guild data.

---

## TODO / Known Issues

1. **Queue pagination** — `/queue` shows max 20 tracks without pagination
2. **Subscription pageToken** — YouTube API pagination not handled (>50 videos)
3. **Potential connection failures** — Not handled gracefully in `subscription.py` and `music.py` (marked with `# TODO` comments)
