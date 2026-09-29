"""Rich text + custom emoji helpers for VJ Join Request Acceptor Bot.

Telegram custom emojis are sent as MessageEntity(CUSTOM_EMOJI) entities wrapped
around their regular fallback emoji. The IDs are sourced from emojisid.txt.
"""
from pyrogram.types import MessageEntity
from pyrogram.enums import MessageEntityType

from plugins.emoji_map import EMOJI_IDS, FALLBACK_IDS


def _utf16_len(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


class RichText:
    def __init__(self, premium: bool = True):
        self.premium = premium
        self.parts = []
        self.entities = []
        self._offset = 0

    def add(self, text: str, style=None):
        if not text:
            return self

        # For premium mode, replace unsupported visuals with a suitable
        # supported fallback whose custom-emoji alt matches the ID. This keeps
        # Telegram's custom emoji entity valid while still showing one emoji.
        if self.premium:
            for source, target in sorted(VISUAL_FALLBACKS.items(), key=lambda x: len(x[0]), reverse=True):
                text = text.replace(source, target)

        start = self._offset
        self.parts.append(text)
        length = _utf16_len(text)
        if style:
            self.entities.append(MessageEntity(type=style, offset=start, length=length))

        if self.premium:
            candidates = sorted(EMOJI_IDS.keys(), key=len, reverse=True)
            pos = 0
            while pos < len(text):
                match = None
                for emoji in candidates:
                    if text.startswith(emoji, pos):
                        match = emoji
                        break
                if match is None:
                    pos += 1
                    continue
                emoji_start = start + _utf16_len(text[:pos])
                emoji_len = _utf16_len(match)
                emoji_id = EMOJI_IDS.get(match) or FALLBACK_IDS.get("default")
                if emoji_id:
                    self.entities.append(
                        MessageEntity(
                            type=MessageEntityType.CUSTOM_EMOJI,
                            offset=emoji_start,
                            length=emoji_len,
                            custom_emoji_id=int(emoji_id),
                        )
                    )
                pos += len(match)
        self._offset += length
        return self

    def line(self, text="", style=None):
        return self.add(text + "\n", style=style)

    def build(self):
        return "".join(self.parts), self.entities


async def premium_enabled(db):
    return bool(await db.get_setting("premium_emojis", True))


# Semantic helpers: if a requested emoji is missing from the supplied list,
# callers can use a suitable known ID instead of creating a second normal emoji.
SEMANTIC = {
    "success": "6267008582294705964",   # ✅
    "danger": "5267123797600783095",    # ❌
    "warning": "6267039884016358504",   # ⚠️
    "info": "6266794310671275367",      # 💬
    "help": "6282525354242348869",      # ❓
    "link": "5316612764427367709",      # 🔗
    "stats": "5877485980901971030",     # 📊
    "settings": "5877260593903177342",  # ⚙
    "lock": "6282846669335702032",      # 🔒
    "rocket": "5316571734604790521",    # 🚀
    "users": "5267440701762735206",     # 👥
    "user": "5316727448644103237",      # 👤
    "broadcast": "5242543510787235019", # 📢
    "channel": "5242543510787235019",  # 📢
    "add": "5274008024585871702",       # ➕
    "time": "5316575093269214796",      # ⏰
    "dead": "6282728866972702273",      # 💀
    "premium": "6264791387032523779",   # 💎
    "fire": "6264785189394717307",      # 🔥
    "trophy": "6266973397922616654",    # 🏆
    "note": "5370546867786523009",      # 📝
    "calendar": "6266947228686892459",  # 🗓
    "star": "6266969287638913443",      # ⭐️
    "hand": "5319007286004299794",      # 👋
    "heart": "6266992763930158001",     # ❤️
}

FALLBACK_IDS.update(SEMANTIC)

# When the requested visual is not present in the supplied list, use the
# closest supported fallback *emoji character* so Telegram's custom-emoji
# entity remains valid (the entity must wrap its matching alt emoji).
VISUAL_FALLBACKS = {
    "🎉": "🎉",
    "🗂": "🗂",
    "🗑": "🗑",
    "🚫": "🚫",
    "⚡": "⚡",
    "✨": "✨",
    "🎯": "⭐️",
    "🔐": "🔒",
    "🆘": "❓",
    "🛠": "⚙",
    "📨": "💬",
    "📅": "🗓",
    "📆": "🗓",
    "📨": "💬",
    "📩": "✉️",
    "⏱": "⏰",
    "🎯": "⭐️",
}
