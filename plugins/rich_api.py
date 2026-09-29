"""Telegram Bot API 10.3 Rich Message bridge.

Pyrofork handles the MTProto side of the bot, while Telegram's newest
Rich Message features are exposed through the Bot API. This module keeps the
rich-message transport isolated and provides a safe fallback to normal
Pyrogram messages when the Rich Message endpoint is unavailable.
"""

import asyncio
import json
import logging
from html import escape

import aiohttp

from config import BOT_TOKEN, RICH_API_TIMEOUT
from plugins.emoji_map import EMOJI_IDS, FALLBACK_IDS
from plugins.rich import VISUAL_FALLBACKS

LOG = logging.getLogger(__name__)
API_ROOT = f"https://api.telegram.org/bot{BOT_TOKEN}"


FALLBACK_VISUALS = {
    "🎉": "🎉",
    "🗂": "📁",
    "🗑": "❌",
    "🚫": "❌",
    "⚡": "⭐️",
    "✨": "⭐️",
    "🛠": "⚙",
    "🔐": "🔒",
    "🆘": "❓",
    "📨": "💬",
    "🎯": "⭐️",
}


def _emoji_alt(emoji: str) -> str:
    if emoji in EMOJI_IDS:
        return emoji
    return VISUAL_FALLBACKS.get(emoji) or FALLBACK_VISUALS.get(emoji) or "✅"


def _emoji_id(emoji: str) -> str:
    # Telegram requires the custom emoji entity to carry the matching alt
    # emoji. Always resolve to an emoji that actually exists in the supplied
    # mapping, rather than pairing a random ID with a different alt.
    alt = _emoji_alt(emoji)
    return str(EMOJI_IDS.get(alt) or FALLBACK_IDS.get("default") or "")


def tg_emoji(emoji: str, label: str | None = None, premium: bool = True) -> str:
    """Return a Rich HTML custom emoji element with one valid alt emoji."""
    alt = _emoji_alt(emoji)
    if not premium:
        return escape(alt)
    emoji_id = _emoji_id(emoji)
    if not emoji_id:
        return escape(alt)
    # Telegram's Rich HTML examples use an emoji alternative inside the tag.
    # Keep exactly one visual emoji as the alternative.
    return f'<tg-emoji emoji-id="{escape(emoji_id)}">{escape(label or alt)}</tg-emoji>'


def rich_button(text: str, *, emoji: str | None = None, kind: str = "callback_data",
                data: str | None = None, url: str | None = None,
                style: str = "primary", premium: bool = True) -> str:
    """Build a native Telegram Rich Message button."""
    inner = f"{tg_emoji(emoji, premium=premium)} {escape(text)}" if emoji else escape(text)
    attrs = [f'type="{escape(kind)}"']
    if style:
        attrs.append(f'style="{escape(style)}"')
    if kind == "callback_data":
        attrs.append(f'data="{escape(data or "")}"')
    elif kind == "url":
        attrs.append(f'url="{escape(url or "")}"')
    elif kind == "copy_text":
        attrs.append(f'text="{escape(data or "")}"')
    return f'<tg-button {" ".join(attrs)}>{inner}</tg-button>'


def rich_button_row(*buttons: str, align: str = "center") -> str:
    return f'<tg-button-row align="{escape(align)}">{"".join(buttons)}</tg-button-row>'


def rich_table(headers, rows, *, bordered=True, striped=True, compact=True, raw=False) -> str:
    attrs = []
    if bordered:
        attrs.append("bordered")
    if striped:
        attrs.append("striped")
    if compact:
        attrs.append("compact")
    html = [f'<table {" ".join(attrs)}>']
    esc = (lambda x: str(x)) if raw else (lambda x: escape(str(x)))
    if headers:
        html.append("<tr>" + "".join(f"<th>{esc(x)}</th>" for x in headers) + "</tr>")
    for row in rows:
        html.append("<tr>" + "".join(f"<td>{esc(x)}</td>" for x in row) + "</tr>")
    html.append("</table>")
    return "".join(html)


async def _call(method: str, payload: dict):
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured")
    timeout = aiohttp.ClientTimeout(total=RICH_API_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(f"{API_ROOT}/{method}", json=payload) as response:
            raw = await response.text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {"ok": False, "description": raw[:500]}
            if not response.ok or not data.get("ok"):
                raise RuntimeError(data.get("description", f"HTTP {response.status}"))
            return data.get("result")


async def send_rich_message(chat_id, html: str, *, disable_notification=False,
                            protect_content=False, reply_parameters=None):
    payload = {
        "chat_id": chat_id,
        "rich_message": {
            "html": html,
            "skip_entity_detection": False,
        },
        "disable_notification": bool(disable_notification),
        "protect_content": bool(protect_content),
    }
    if reply_parameters:
        payload["reply_parameters"] = reply_parameters
    return await _call("sendRichMessage", payload)


async def edit_rich_message(chat_id, message_id, html: str):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "rich_message": {
            "html": html,
            "skip_entity_detection": False,
        },
    }
    return await _call("editMessageText", payload)


async def answer_callback(callback_query_id, text=None, show_alert=False):
    payload = {"callback_query_id": callback_query_id, "show_alert": bool(show_alert)}
    if text:
        payload["text"] = text
    return await _call("answerCallbackQuery", payload)



def strip_custom_emoji_tags(html: str) -> str:
    """Remove custom-emoji wrappers but keep their normal fallback emoji."""
    import re
    return re.sub(r'<tg-emoji\b[^>]*>(.*?)</tg-emoji>', r'\1', html, flags=re.DOTALL)


def rich_supported_html(html: str) -> str:
    """Normalize a few unsafe/unsupported characters before sending HTML."""
    # Rich HTML is already built from escaped user values. This helper is kept
    # intentionally small so it never double-escapes the rich tags.
    return html


async def safe_send_rich(client, chat_id, html: str, *, fallback=None,
                         reply_markup=None, disable_notification=False):
    """Send Rich Message; optionally fall back to Pyrogram on Bot API failure."""
    try:
        return await send_rich_message(
            chat_id,
            rich_supported_html(html),
            disable_notification=disable_notification,
        )
    except Exception as exc:
        # If custom-emoji permission is the blocker, retry the same Rich
        # Message with normal emoji fallbacks. Tables, slideshow, details and
        # native rich buttons still remain intact.
        try:
            plain_rich = strip_custom_emoji_tags(html)
            return await send_rich_message(
                chat_id,
                plain_rich,
                disable_notification=disable_notification,
            )
        except Exception as rich_exc:
            LOG.warning("Rich Message send failed; using fallback: %s / %s", exc, rich_exc)
            if fallback is None:
                raise
            text, entities = fallback
            return await client.send_message(
                chat_id,
                text,
                entities=entities,
                reply_markup=reply_markup,
                disable_notification=disable_notification,
            )


async def safe_edit_rich(client, chat_id, message_id, html: str, *, fallback=None,
                         reply_markup=None):
    try:
        return await edit_rich_message(chat_id, message_id, rich_supported_html(html))
    except Exception as exc:
        try:
            return await edit_rich_message(chat_id, message_id, strip_custom_emoji_tags(html))
        except Exception as rich_exc:
            LOG.warning("Rich Message edit failed; using fallback: %s / %s", exc, rich_exc)
            if fallback is None:
                raise
            text, entities = fallback
            return await client.edit_message_text(
                chat_id,
                message_id,
                text,
                entities=entities,
                reply_markup=reply_markup,
            )
