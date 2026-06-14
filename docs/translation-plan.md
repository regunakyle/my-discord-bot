# Translation Cog — Plan

> Auto-translate messages between a Chinese channel and an English channel via emote reactions and reply chains.

## Flow

1. Admin configures a trigger emote + two channels (Chinese + English) via `/translation_setup`.
2. A user reacts with the trigger emote on a message in one channel → bot adds an acknowledgment emoji (placeholder), translates the message, and posts it to the other channel with a `[TRANSLATION]` header.
3. A user replies to any bot message carrying the `[TRANSLATION]` header → bot translates the reply and posts it to the opposite channel, again with a `[TRANSLATION]` header. This continues indefinitely.

---

## Step 1 — New Database Model: `Translation`

**File**: `src/my_discord_bot/models/translation.py`

| Column | Type | Notes |
|---|---|---|
| `id` | `int` (PK, auto) | |
| `guild_id` | `int` (FK → `guild.id`, CASCADE delete) | One row per guild |
| `trigger_emote` | `str` | Stored as `<a:name:id>` or `<:name:id>` (custom emote) or the raw Unicode emoji (e.g. `🔄`) |
| `chinese_channel_id` | `int` | Discord channel ID |
| `english_channel_id` | `int` | Discord channel ID |

### Guild Relationship

Add to `models/guild.py`:

```python
translation: Mapped["Translation | None"] = relationship(
    back_populates="guild",
    lazy="raise",
    cascade="save-update, merge, delete",
    uselist=False,
)
```

### Exports & Migration

- Export `Translation` from `models/__init__.py`
- Add `translation` relationship import to `models/guild.py` (TYPE_CHECKING block)
- Generate migration: `alembic revision --autogenerate -m "add translation table"`

---

## Step 2 — Extract Generic OpenAI Call into `CogBase`

**File**: `src/my_discord_bot/cogs/_cog_base.py`

Add a shared async method and a placeholder constant:

```python
ACK_EMOJI = "✅"  # Placeholder — bot owner will change this

async def call_openai(
    self,
    messages: list[dict[str, str]],
) -> str | None:
    """Make a generic OpenAI API call. Returns the assistant's text, or None on failure."""
```

Implementation:
- Uses `openai.AsyncOpenAI()` with `OPENAI_API_KEY` + `OPENAI_MODEL_NAME`
- `base_url` from `OPENAI_BASE_URL` (None if not set → official endpoint)
- Calls `client.responses.create(model=..., input=messages)`
- Returns the response text, or `None` if the API call fails (log error)
- **Callers are responsible for** constructing the `messages` list (system prompt, user content, etc.)

`ai.py` is **not changed** — it handles its own chat flow with the brave_search tool. The Translation cog uses `call_openai` for simple translation prompts.

---

## Step 3 — Translation Cog: Setup Commands

**File**: `src/my_discord_bot/cogs/translation.py`

### `/translation_setup <emote> <chinese_channel> <english_channel>`

- **Admin-only** (`has_permissions(manage_channels=True)`)
- `emote`: string in format `<a:name:id>`, `<:name:id>`, or a raw Unicode emoji
- `chinese_channel` / `english_channel`: resolved via `discord.app_commands.channel()`
- Validates: two channels are different, both belong to the current guild
- Upserts the `Translation` row for the guild
- Confirms settings on success

### `/translation_status`

- Shows current trigger emote, Chinese channel, English channel — or "not configured"

### `/translation_reset`

- Admin-only. Deletes the `Translation` row for the guild.

---

## Step 4 — Reaction Listener: `on_reaction_add`

```python
@commands.Cog.listener()
async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
```

### Flow

1. **Skip bots**: `if user.bot: return`
2. **Skip DMs**: `if not reaction.message.guild: return`
3. **Load config**: Query `Translation` by guild (joinedload nothing needed — flat row). If none, return.
4. **Match trigger emote**: Parse stored `trigger_emote` and compare against `reaction.emoji` — see [Emote Matching](#emote-matching) below.
5. **Check channel**: `reaction.message.channel.id` must be one of `{chinese_channel_id, english_channel_id}`. If not, return.
6. **Ack check**: Scan `reaction.message.reactions` for `ACK_EMOJI`. If present, skip (already processed).
7. **Add ack**: `await reaction.message.add_reaction(ACK_EMOJI)`
8. **Determine direction**:
   - Message in Chinese channel → translate to `"Traditional Chinese"`, target = English channel
   - Message in English channel → translate to `"English"`, target = Chinese channel
9. **Build translated message**:
   - Extract original text from `reaction.message.content`
   - If text is empty (embed/attachment only), forward as-is with `[TRANSLATION]` header and skip AI call
   - Otherwise, build messages list:
     ```python
     messages = [
         {"role": "system", "content": f"You are a translator. Translate the following text to {target_language}. Output ONLY the translated text, nothing else."},
         {"role": "user", "content": text},
     ]
     translated = await self.call_openai(messages)
     ```
   - If `translated` is None (API failed): send "Translation failed" notice in the **source channel** (where the reaction happened), return
   - Compose message:
     ```
     [TRANSLATION] forwarded from #{source_channel_name} by {author.display_name}

     {translated_text}
     ```
   - Attach original message's files (fetch via `message.attachments` → download → `discord.File`)
   - Attach original message's embeds
10. **Send** to target channel via `target_channel.send()`

### Emote Matching

Parse the stored `trigger_emote` string:

| Stored format | Parse | Match against |
|---|---|---|
| `<a:name:123>` or `<:name:123>` | `emoji_name="name"`, `emoji_id=123` | `reaction.emoji.name == emoji_name` AND `reaction.emoji.id == 123` |
| Raw string (no `<` / `>`) | Treat as Unicode emoji | `str(reaction.emoji) == stored_string` |

Use a helper function:

```python
def emote_matches(stored: str, emoji: discord.Emoji | discord.PartialEmoji) -> bool:
```

---

## Step 5 — Reply Listener: `on_message`

```python
@commands.Cog.listener()
async def on_message(self, message: discord.Message):
```

### Flow

1. **Skip bots and DMs**: `if message.author.bot or not message.guild: return`
2. **Check for reply**: `message.reference` must exist and `message.reference.resolved` must be a bot message (check `resolved.author.bot`).
3. **Check for `[TRANSLATION]` flag**: The replied-to message's content must start with `[TRANSLATION]`. If not, return.
4. **Load config**: Query `Translation` by guild. If none, return.
5. **Verify channel**: `message.channel.id` must be one of the two configured channels. If not, return.
6. **Determine direction** (same logic as reaction listener):
   - Message in Chinese channel → translate to `"English"`, target = English channel
   - Message in English channel → translate to `"Traditional Chinese"`, target = Chinese channel
7. **Translate and forward**:
   - Build messages list with system prompt + user content (same pattern as Step 4)
   - `translated = await self.call_openai(messages)`
   - If None: **log error silently** — do not send any error message to the user
   - Compose message with `[TRANSLATION]` header (same format as Step 4)
   - Forward attachments and embeds
   - Send to target channel

This creates the infinite translation chain: each translated message carries `[TRANSLATION]`, so replies to it are caught again.

---

## Step 6 — Conditional Cog Loading

In `bot.py` `setup_hook()`, add:

```python
if cog.__name__ == "Translation" and not (
    len(os.getenv("OPENAI_API_KEY", ""))
    and len(os.getenv("OPENAI_MODEL_NAME", ""))
):
    continue
```

Same requirement as the AI cog — needs OpenAI credentials.

---

## Step 7 — Update `cogs/__init__.py`

- Import `Translation` from `.translation`
- Add `Translation` to `cog_list`
- Add `"Translation"` to `__all__`
- Remove the old empty `Podcast` cog file and its references

---

## Edge Cases

| Scenario | Handling |
|---|---|
| Translation API fails (emoji-triggered) | Log error, send "Translation failed" in source channel |
| Translation API fails (reply-triggered) | Log error silently — no message sent to user |
| Translated text > 2000 chars | Truncate to 2000 (same pattern as `ai.py`) |
| Original message is empty (embed/attachment only) | Forward as-is with `[TRANSLATION]` header, no AI call |
| Both channels are the same | Reject in `/translation_setup` |
| Bot restarts | Ack emojis persist on messages (they're on Discord). No in-memory state to lose. |
| User removes ack emoji | If trigger emote is re-added, no ack emoji found → message re-translates. Acceptable. |
| Reply to a reply (nested replies) | `message.reference.resolved` points to the direct parent. If that parent has `[TRANSLATION]`, it triggers. Works correctly. |
| Message in non-configured channel | Silently ignored in both listeners |

---

## Files to Create/Modify

| File | Action |
|---|---|
| `src/my_discord_bot/models/translation.py` | **Create** — `Translation` model |
| `src/my_discord_bot/models/__init__.py` | **Modify** — export `Translation` |
| `src/my_discord_bot/models/guild.py` | **Modify** — add `translation` relationship |
| `src/my_discord_bot/cogs/_cog_base.py` | **Modify** — add `translate_text()` + `ACK_EMOJI` |
| `src/my_discord_bot/cogs/translation.py` | **Create** — full cog (commands + listeners) |
| `src/my_discord_bot/cogs/podcast.py` | **Delete** — replaced by `translation.py` |
| `src/my_discord_bot/cogs/__init__.py` | **Modify** — swap `Podcast` → `Translation` |
| `src/my_discord_bot/cogs/ai.py` | **Modify** — use `self.translate_text()` from base |
| `src/my_discord_bot/bot.py` | **Modify** — conditional loading for `Translation` |
| `migrations/versions/xxxx_add_translation.py` | **Create** — Alembic migration (auto-generated) |
