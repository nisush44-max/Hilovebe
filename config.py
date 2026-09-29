from os import environ

API_ID = int(environ.get("API_ID", "37502609"))
API_HASH = environ.get("API_HASH", "cd4e39a4344aad8946b904292abbdf14")
BOT_TOKEN = environ.get("BOT_TOKEN", "8611961334:AAGAdtZtIqo9u083Wo_eEnAgcGJKCmYoXFk")

LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1003835007743"))

# Supports one admin ID or comma-separated IDs: 123,456,789
_raw_admins = environ.get("ADMINS", "8363262755")
ADMINS = [int(x.strip()) for x in _raw_admins.split(",") if x.strip().lstrip("-").isdigit()]
if not ADMINS:
    ADMINS = [8363262755]

DB_URI = environ.get("DB_URI", "mongodb+srv://nnr4lxwdkasdev_db_user:mwsnTzZuTX8b7Kou@cluster0.76bddsl.mongodb.net")
DB_NAME = environ.get("DB_NAME", "vjjoinrequetbot")
NEW_REQ_MODE = environ.get("NEW_REQ_MODE", "false").strip().lower() in ("1", "true", "yes", "on")

# Telegram Bot API Rich Message transport. Bot API 10.1+ is required.
RICH_API_TIMEOUT = float(environ.get("RICH_API_TIMEOUT", "25"))

# Six default slideshow images. Replace with your own HTTPS image URLs using
# RICH_SLIDESHOW_IMAGES separated by | for a branded carousel.
DEFAULT_RICH_SLIDESHOW_IMAGES = [
    "https://i.ibb.co/BVsKnyNV/064f96dfff4d.jpg",
    "https://i.ibb.co/PzV2h70D/f82c0c3e9c17.jpg",
    "https://i.ibb.co/zVj5TfPS/680e457de374.jpg",
    "https://i.ibb.co/hRCHVncn/6c5a3f7cd119.jpg",
    "https://i.ibb.co/p6ZYxNkK/edb9f72291d2.jpg",
    "https://i.ibb.co/KpvT8Fds/fa35b230361b.jpg",
]
RICH_SLIDESHOW_IMAGES = [
    x.strip() for x in environ.get("RICH_SLIDESHOW_IMAGES", "").split("|")
    if x.strip()
] or DEFAULT_RICH_SLIDESHOW_IMAGES

# Rich Message callback polling is intentionally Bot API based because native
# Rich buttons are delivered as Bot API callback_query updates.
RICH_CALLBACK_POLL_TIMEOUT = int(environ.get("RICH_CALLBACK_POLL_TIMEOUT", "25"))
