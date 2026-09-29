# VJ Join Request Acceptor Bot — Advanced Rich UI

This version keeps the original join-request workflow and adds a rich Telegram UI.

## Main features
- Channel + Group join-request acceptance
- User Telegram account login/session flow
- `/accept`, `/mystats`, `/logout`
- Final acceptance report in the chat **and a separate DM**
- Today: total / success / dead / error statistics
- Advanced admin panel and broadcast tools
- Premium custom-emoji rich messages using the supplied `emojisid.txt`
- Premium emoji mode can be toggled from `/admin`
- When Premium Emoji mode is OFF, the same messages use normal fallback emojis only
- When an emoji is not present in the supplied list, the renderer uses a suitable supported visual fallback; it never creates a second normal+premium emoji pair
- Rich photo start message with boxed/table-style text
- URL buttons for Add To Channel, Add To Group, Update Channel and Support Group
- Callback/command-style buttons for Help, Login, Accept and Stats

## Environment variables
`API_ID`, `API_HASH`, `BOT_TOKEN`, `DB_URI`, `DB_NAME`, `LOG_CHANNEL`, `ADMINS`, `NEW_REQ_MODE`

## Render
Recommended start command:

```bash
gunicorn app:app & python3 bot.py
```

Python version is pinned in `.python-version`.

## Premium emoji implementation
Telegram custom emojis are sent as `MessageEntity` objects with `CUSTOM_EMOJI` and a `custom_emoji_id`. The entity wraps the matching regular fallback emoji, as required by Telegram.

## Telegram Rich Message UI (Bot API 10.1+)

This version uses Telegram's native Rich Message API for the main user/admin UI. It adds:
- native swipeable `<tg-slideshow>` with up to 6 HTTPS images
- real Rich Message tables and expandable `<details>` sections
- native Rich Message buttons with callback/URL actions and button styles
- custom-emoji icons inside rich buttons when the bot is permitted to use custom emojis
- normal-emoji Rich Message fallback if Telegram rejects custom emoji permission
- normal Pyrogram fallback only if the Rich Message endpoint itself is unavailable

### Slideshow branding
Set `RICH_SLIDESHOW_IMAGES` to your own HTTPS image URLs separated with `|`:

```text
RICH_SLIDESHOW_IMAGES=https://example.com/1.jpg|https://example.com/2.jpg|https://example.com/3.jpg|https://example.com/4.jpg|https://example.com/5.jpg|https://example.com/6.jpg
```

The start/help/stats/accept/admin/broadcast screens use Rich Message tables and controls. The Login / Accept / Stats controls are intentionally inside Help instead of the start screen.

Telegram added Rich Messages in Bot API 10.1 and expanded Rich Message buttons/tables in later Bot API releases. A current Telegram Bot API is required for the native rich UI.


## Render startup fix

This bot is server-safe: it refuses to start if `API_ID`, `API_HASH`, or `BOT_TOKEN` is missing instead of opening Pyrogram's interactive `Enter phone number or bot token:` prompt. Set those variables in Render → Environment and redeploy. Rich Message callbacks are handled through a dedicated Bot API `getUpdates` poller.

The start Rich Message uses the six slideshow images from the supplied ProRichBypassBot source by default; override them with `RICH_SLIDESHOW_IMAGES` as `URL1|URL2|...|URL6`.
