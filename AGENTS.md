# AGENTS.md — Reguna's Discord Bot

> Reference guide for AI agents implementing new features.

## Project Overview

A personal Discord bot written in **Python 3.13** using **discord.py** with slash commands. Data is persisted in **SQLite3** via **SQLAlchemy (async)** with **Alembic** migrations. The bot is deployable both natively and via **Docker Compose** (with a bundled Lavalink music node).

- **Package name**: `my-discord-bot` (in `src/my_discord_bot/`)
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
│   ├── meta.py          # >>sync, /help, /set_bot_channel, /set_welcome_message, /version
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
- **`on_member_join()`**: Sends welcome message if configured
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
- `get_max_file_size(guild)` — returns Discord's upload limit capped by `MAX_FILE_SIZE` env var, based on guild Nitro level
- `check_cooldown_factory(seconds)` — returns a dynamic cooldown check that **exempts the bot owner**

### Database Models

**`Guild`** (`models/guild.py`):

- `id` (auto-increment PK), `guild_id` (unique Discord snowflake), `guild_name`, `bot_channel` (nullable channel ID), `welcome_message` (nullable, max 2000 chars)
- Relationship: `subscriptions` (one-to-many, `lazy="raise"`, cascade delete)
- Relationship: `translation` (one-to-zero-or-one, `lazy="raise"`, cascade delete)

**`Subscription`** (`models/subscription.py`):

- `id` (auto-increment PK), `guild_id` (FK → guild.id, cascade delete), `youtube_channel_name`, `youtube_channel_id` (unique), `youtube_upload_playlist`, `announcement_target` (nullable role ID string), `last_checked_at`
- Relationship: `guild` (many-to-one, `lazy="raise"`)

**`Translation`** (`models/translation.py`):

- `id` (auto-increment PK), `guild_id` (FK → guild.id, unique, cascade delete), `trigger_emote`, `chinese_channel_id`, `english_channel_id`
- Relationship: `guild` (many-to-one, `lazy="raise"`)

**Adding a new model**:

1. Create file in `models/` inheriting from `ModelBase`
2. Export from `models/__init__.py`
3. Generate migration: `alembic revision --autogenerate -m "description"`
4. Review and commit the migration file

### Global Error Handling (`error_handler.py`)

`ErrorHandler` cog registers `self.bot.tree.on_error = self.on_app_command_error` in its constructor. It catches:

- `MissingPermissions` → "You don't have the required permission!"
- `NoPrivateMessage` → "This command is only available inside a server!"
- `CommandOnCooldown` → Shows cooldown message
- `CommandInvokeError` with error code 40005 → File too large message
- `CommandInvokeError` wrapping `GuildNotFoundError` → Auto-inserts guild into DB, asks user to retry
- All other errors → "Something unexpected happened!" + error.jpg

It handles both `ia.response.send_message()` and `ia.followup.send()` (for already-responded interactions).

---

## Cog Details

### General (`general.py`)

| Command | Description |
|---|---|
| `/hello` | Sends `assets/images/hello.jpg` |
| `/pixiv [pixiv_link] <image_number> <animation_format>` | Downloads Pixiv images via `gallery-dl`. Requires ffmpeg + OAuth token. 3-second cooldown. Guild-only. Supports `webm`/`gif` animation format. |

Key details:

- Uses `gallery-dl` library directly (config + `DownloadJob`)
- Max file size respects guild Nitro level + `MAX_FILE_SIZE` env var
- Defer response (up to 15 min processing time)

### Meta (`meta.py`)

| Command | Description |
|---|---|
| `>>sync` (hybrid, owner-only) | Re-syncs slash commands globally + syncs guild DB records |
| `/help <command_name>` | Lists all commands or details for a specific command |
| `/set_bot_channel` (admin) | Sets/unsets current channel as bot notification channel |
| `/set_welcome_message` (admin) | Sets welcome message for new members (supports `\n`, `<#channel>`, `<@user>`, `<a:emoji:id>`) |
| `/version` | Reports bot version (checks `APP_VERSION` env → git branch → pyproject.toml) |

### AI (`ai.py`)

| Command | Description |
|---|---|
| `/chat [message]` | Sends message to OpenAI-compatible API. 1.5-second cooldown. Guild-only. |

Key details:

- Uses `openai.AsyncOpenAI()` client
- Model name from `OPENAI_MODEL_NAME` env var
- Base URL from `OPENAI_BASE_URL` env var (if empty, uses official OpenAI endpoint; the env var is deleted in `setup_hook` if empty)
- Uses `client.responses.create()` API with a `brave_search` function tool
- Response truncated to 2000 chars per message (splits into multiple messages if longer)

### Music (`music.py`)

| Command | Description |
|---|---|
| `/play [query]` | Searches and enqueues a track (YouTube via Lavalink) |
| `/quit` | Clears queue, stops playback, disconnects from voice |
| `/queue` | Shows current queue (max 20 tracks displayed) |
| `/pause` | Toggle pause/resume |
| `/loop` | Toggle single-track loop |
| `/skip` | Skip current track (also cancels loop) |

Key details:

- Uses `lavalink` library (v5.x) with custom `LavalinkVoiceClient(discord.VoiceProtocol)`
- `create_player_check` — shared pre-command check that validates voice channel state, permissions, and creates Lavalink player
- Lavalink client stored on `bot.lavalink` (dynamic attribute)
- Background task `leave_inactive_voice_channel_task` (1-min loop): disconnects if no non-bot users in voice channel
- Event hooks: `TrackStartEvent`, `QueueEndEvent`, `TrackLoadFailedEvent`, `NodeReadyEvent`, `NodeDisconnectedEvent`
- Query prefix `ytsearch:` auto-added for non-URL queries

### Subscription (`subscription.py`)

| Command | Description |
|---|---|
| `/subscribe [channel_id] <target_role_id>` (admin) | Subscribe/unsubscribe to YouTube channel for live stream notifications |

Key details:

- Uses `googleapiclient.discovery.build("youtube", "v3")` with `GOOGLE_API_KEY`
- Background task `check_subscription` (15-min loop): polls YouTube playlist items for new uploads, checks if they are scheduled live streams, posts announcement to bot channel
- Timezone conversion: UTC → Asia/Hong_Kong (UTC+8)
- `last_checked_at` prevents re-notifying for already-seen videos
- Announcement pings `target_role_id` or `@everyone` if not specified

### Translation (`translation.py`)

| Command | Description |
|---|---|
| `/translation_setup <emote> <chinese_channel> <english_channel>` (admin) | Configure translation between two channels |
| `/translation_status` | Show current translation configuration |
| `/translation_reset` (admin) | Reset translation configuration |

Key details:

- **Trigger mechanism**: Reacting with the configured `trigger_emote` on a message in either channel translates it to the other channel. Replying to a `[TRANSLATION]` bot message continues the chain.
- **Streaming**: Uses `call_openai_stream()` from `CogBase` — sends an initial message and edits in real-time as chunks arrive, splitting across reply messages when exceeding 2000 characters.
- **Header format**: `TRANSLATION_HEADER_TEMPLATE.format(chain_id)` → `[TRANSLATION] <8-char-hex>` (defined in `constants.py`). The ack emoji (`ACK_EMOJI` = ✅) prevents duplicate processing.
- **Direction**: Chinese channel → English, English channel → Traditional Chinese. Reply chains always flip direction (since replies must be in the same channel as the original).
- **No file forwarding**: Attachments are not forwarded to the target channel.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | **Yes** | Bot token |
| `PREFIX` | **Yes** | Command prefix (default `>>`); currently only used by `>>sync` |
| `LOG_LEVEL` | No | `DEBUG`, `INFO`, `WARNING`, etc. (default `INFO`) |
| `MAX_FILE_SIZE` | No | Max upload size in MiB (default `10`) |
| `LAVALINK_URL` | No* | Lavalink server URL (e.g., `http://localhost:2333`) |
| `LAVALINK_PASSWORD` | No* | Lavalink password (default `youshallnotpass`) |
| `OPENAI_API_KEY` | No* | OpenAI API key (or any string for custom endpoints) |
| `OPENAI_MODEL_NAME` | No* | Model name (default `gpt-3.5-turbo`) |
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

### CI/CD

GitHub Actions (`.github/workflows/docker.yaml`) builds and pushes to Docker Hub on pushes to `master` (tag: `latest`) and `dev` (tag: `dev`).

### After Updates

Always run `>>sync` in Discord after deploying updates to re-register slash commands and sync guild data.

---

## TODO / Known Issues

1. **Streaming AI responses** — `/chat` should stream chunks instead of sending full response
2. **Queue pagination** — `/queue` shows max 20 tracks without pagination
3. **Subscription pageToken** — YouTube API pagination not handled (>50 videos)
4. **Potential connection failures** — Not handled gracefully in `subscription.py` and `music.py`
