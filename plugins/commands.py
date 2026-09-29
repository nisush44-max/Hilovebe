import asyncio
import logging
import time
from html import escape

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, RPCError, UserNotParticipant
from pyrogram.enums import MessageEntityType

from config import LOG_CHANNEL, API_ID, API_HASH, NEW_REQ_MODE, ADMINS, RICH_SLIDESHOW_IMAGES
from plugins.database import db
from plugins.rich import RichText, premium_enabled
from plugins.rich_api import (
    safe_send_rich,
    safe_edit_rich,
    rich_button,
    rich_button_row,
    rich_table,
    tg_emoji,
)

LOG_TEXT = """<b>#NewUser\n\nID - <code>{}</code>\n\nNᴀᴍᴇ - {}</b>"""
START_IMAGE = "https://te.legra.ph/file/119729ea3cdce4fefb6a1.jpg"

# Six image slots. Users can replace these with their own HTTPS images through
# RICH_SLIDESHOW_IMAGES=URL1|URL2|...|URL6. Telegram renders them as a native
# swipeable rich-message slideshow.
DEFAULT_SLIDES = [
    "https://i.ibb.co/BVsKnyNV/064f96dfff4d.jpg",
    "https://i.ibb.co/PzV2h70D/f82c0c3e9c17.jpg",
    "https://i.ibb.co/zVj5TfPS/680e457de374.jpg",
    "https://i.ibb.co/hRCHVncn/6c5a3f7cd119.jpg",
    "https://i.ibb.co/p6ZYxNkK/edb9f72291d2.jpg",
    "https://i.ibb.co/KpvT8Fds/fa35b230361b.jpg",
]
SLIDES = (RICH_SLIDESHOW_IMAGES[:6] if RICH_SLIDESHOW_IMAGES else DEFAULT_SLIDES)
if len(SLIDES) < 6:
    SLIDES = (SLIDES + DEFAULT_SLIDES)[:6]



def start_keyboard(username):
    """Fallback only. The normal UI uses native Rich Message buttons."""
    username = (username or "RequestApprovalBot").lstrip("@")
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add To Channel", url=f"https://t.me/{username}?startchannel=true"),
            InlineKeyboardButton("➕ Add To Group", url=f"https://t.me/{username}?startgroup=true"),
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="cmd:help"),
            InlineKeyboardButton("🤖 Shop", url="https://t.me/shopsynax"),
        ],
        [
            InlineKeyboardButton("📢 Update Channel", url="https://t.me/SynaxBotz"),
            InlineKeyboardButton("📢 Support Group", url="https://t.me/SynaxSupport"),
        ],
    ])


def _slide_html():
    images = []
    for url in SLIDES[:6]:
        if not url.startswith(("https://", "http://")):
            continue
        images.append(f'<img src="{escape(url, quote=True)}"/>')
    return f'<tg-slideshow>{"".join(images)}<figcaption>Synax Join Request Acceptor • Swipe to explore</figcaption></tg-slideshow>'


def _user_emoji(emoji, enabled):
    return tg_emoji(emoji, premium=enabled)


def _rich_nav_buttons(username, enabled):
    username = (username or "RequestApprovalBot").lstrip("@")
    return "".join([
        rich_button("Add To Channel", emoji="➕", kind="url", url=f"https://t.me/{username}?startchannel=true", style="success", premium=enabled),
        rich_button("Add To Group", emoji="➕", kind="url", url=f"https://t.me/{username}?startgroup=true", style="success", premium=enabled),
    ])


def _rich_small(text):
    """Render compact helper text in Rich Message markup."""
    return f"<small>{text}</small>"


def _rich_quote(text):
    """Render a compact quoted Rich Message block."""
    return f"<blockquote>{_rich_small(text)}</blockquote>"


def build_start_html(name, username, premium=True):
    n = escape(name or "there")
    bot_username = (username or "RequestApprovalBot").lstrip("@")

    # Keep the hero area compact: title -> fast subtitle -> one-line welcome.
    title = f'{_user_emoji("💎", premium)} <b>SYNAX JOIN REQUEST HUB</b>'
    fast_line = (
        f'{_user_emoji("⚡", premium)} '
        f'<i>Fast • clean • secure join-request processing</i>'
    )
    welcome_line = f'{_user_emoji("👋", premium)} <b>Welcome, {n}!</b>'

    feature_rows = [
        (_user_emoji("🚀", premium), "Fast pending-request approval"),
        (_user_emoji("🔗", premium), "Channel + Group workflow"),
        (_user_emoji("📊", premium), "Per-account live statistics"),
        (_user_emoji("✨", premium), "Native Telegram Rich Message UI"),
        (_user_emoji("🔒", premium), "Protected login/session flow"),
    ]

    html = [
        _slide_html(),

        # Clean one-line title.
        f'{title}\n',

        # Small Rich text line for the "Fast" description.
        f'{_rich_small(fast_line)}\n',

        # Welcome stays on one compact line.
        f'{welcome_line}\n',

        # Management description is now a small quoted Rich block.
        _rich_quote(
            f'{_user_emoji("📝", premium)} '
            f'<b>Manage</b> pending join requests from your own Telegram account '
            f'with a structured, swipeable and interactive interface.'
        ),

        # Rich feature box/table remains intact.
        '<details open><summary><b>LIVE FEATURES</b></summary>',
        _rich_small("A compact overview of the main request-processing features."),
        rich_table(["Feature", "What it does"], feature_rows, raw=True),
        '</details>',

        # Rich account-flow box/table remains intact.
        '<details><summary><b>ACCOUNT FLOW</b></summary>',
        _rich_small("Simple 4-step flow from login to the final target report."),
        rich_table(["Step", "Action"], [
            (f'{_user_emoji("1️⃣", premium)} 01', 'Open Help'),
            (f'{_user_emoji("2️⃣", premium)} 02', 'Login your Telegram account'),
            (f'{_user_emoji("3️⃣", premium)} 03', 'Accept requests from one target chat'),
            (f'{_user_emoji("4️⃣", premium)} 04', 'Receive that target chat\'s final report'),
        ], raw=True),
        '</details>',

        # Small quoted note instead of a large standalone sentence.
        _rich_quote(
            f'{_user_emoji("✨", premium)} '
            f'<b>All main actions</b> are available through Telegram Rich Message buttons.'
        ),

        # Existing action rows are preserved.
        rich_button_row(*[
            rich_button(
                "Help",
                emoji="❓",
                data="cmd:help",
                style="primary",
                premium=premium,
            ),
            rich_button(
                "Shop",
                emoji="🤖",
                kind="url",
                url="https://t.me/ShopSynax",
                style="primary",
                premium=premium,
            ),
        ]),
        rich_button_row(*[
            rich_button(
                "Update Channel",
                emoji="📢",
                kind="url",
                url="https://t.me/synaxbotz",
                style="success",
                premium=premium,
            ),
            rich_button(
                "Support Group",
                emoji="📢",
                kind="url",
                url="https://t.me/synaxsupport",
                style="success",
                premium=premium,
            ),
        ]),
        rich_button_row(*[
            rich_button(
                "Add To Channel",
                emoji="➕",
                kind="url",
                url=f"https://t.me/{bot_username}?startchannel=true",
                style="danger",
                premium=premium,
            ),
            rich_button(
                "Add To Group",
                emoji="➕",
                kind="url",
                url=f"https://t.me/{bot_username}?startgroup=true",
                style="danger",
                premium=premium,
            ),
        ]),
    ]

    return "".join(html)

def build_help_html(username, premium=True):
    username = (username or "RequestApprovalBot").lstrip("@")
    return "".join([
        '<b>', _user_emoji("❓", premium), ' <b>HELP • CONTROL CENTER</b></b>\n',
        '<i>The old Login / Accept / Stats row is intentionally moved here.</i>\n',
        '<details open><summary><b>HOW TO USE</b></summary>',
        rich_table(["Step", "Do this"], [
            (f'{_user_emoji("1️⃣", premium)}', 'Add the bot as admin to the target channel/group.'),
            (f'{_user_emoji("2️⃣", premium)}', 'Press Login and connect your Telegram account.'),
            (f'{_user_emoji("3️⃣", premium)}', 'Press Accept and forward one message from the target chat.'),
            (f'{_user_emoji("4️⃣", premium)}', 'The bot processes only that selected target.'),
            (f'{_user_emoji("5️⃣", premium)}', 'After completion, you receive that target\'s individual result report.'),
        ], raw=True),
        '</details>',
        '<details><summary><b>COMMANDS</b></summary>',
        rich_table(["Command", "Purpose"], [
            ('/login', 'Connect Telegram account'),
            ('/accept', 'Process one selected target chat'),
            ('/mystats', 'Show today\'s account stats'),
            ('/logout', 'Remove saved session'),
        ]),
        '</details>',
        '<b>Rich controls</b> use native Telegram buttons with optional custom-emoji icons and button styles.\n',
        rich_button_row(
            rich_button("Login", emoji="🔐", data="cmd:login", style="success", premium=premium),
            rich_button("Accept", emoji="🚀", data="cmd:accept", style="primary", premium=premium),
            rich_button("Stats", emoji="📊", data="cmd:stats", style="danger", premium=premium),
        ),
        rich_button_row(
            rich_button("Add To Channel", emoji="➕", kind="url", url=f"https://t.me/{username}?startchannel=true", style="success", premium=premium),
            rich_button("Add To Group", emoji="➕", kind="url", url=f"https://t.me/{username}?startgroup=true", style="success", premium=premium),
        ),
        rich_button_row(
            rich_button("Support", emoji="📢", kind="url", url="https://t.me/SynaxSupport", style="danger", premium=premium),
            rich_button("Updates", emoji="📢", kind="url", url="https://t.me/SynaxBotz", style="danger", premium=premium),
        ),
    ])


def build_action_html(title, body, premium=True):
    return "".join([
        f'<b>{_user_emoji("🚀" if "Accept" in title else "🔐", premium)} <b>{escape(title)}</b></b>\n',
        f'{escape(body)}\n',
        rich_button_row(rich_button("Help", emoji="❓", data="cmd:help", style="primary", premium=premium)),
    ])


def build_stats_html(stats, title="Today's Join Request Stats", premium=True):
    total = int(stats.get("total", 0))
    success = int(stats.get("success", 0))
    dead = int(stats.get("dead", 0))
    error = int(stats.get("error", 0))
    return "".join([
        f'<b>{_user_emoji("📊", premium)} <b>{escape(title)}</b></b>\n',
        rich_table(["Status", "Count"], [
            (f'{_user_emoji("📨", premium)} Total', total),
            (f'{_user_emoji("✅", premium)} Success', success),
            (f'{_user_emoji("💀", premium)} Dead', dead),
            (f'{_user_emoji("⚠️", premium)} Error', error),
        ], raw=True),
        '<details><summary><b>ACCOUNT STATUS</b></summary>',
        f'{_user_emoji("💎", premium)} <b>Rich UI:</b> {"Premium custom emojis" if premium else "Normal emoji mode"}\n',
        '</details>',
        rich_button_row(
            rich_button("Help", emoji="❓", data="cmd:help", style="link", premium=premium),
            rich_button("Accept", emoji="🚀", data="cmd:accept", style="primary", premium=premium),
        ),
    ])


def build_accept_report_html(result, seconds, chat_title, chat_type, stats, premium=True):
    title = escape(chat_title or "Unknown Chat")
    return "".join([
        f'<b>{_user_emoji("🎉", premium)} <b>ACCEPT COMPLETE</b></b>\n',
        f'{_user_emoji("📣", premium)} <b>Target:</b> {title}\n{_user_emoji("🗂", premium)} <b>Type:</b> {escape(chat_type)}\n',
        '<details open><summary><b>TARGET RESULT</b></summary>',
        rich_table(["Metric", "Result"], [
            (f'{_user_emoji("📨", premium)} Attempted', result['attempted']),
            (f'{_user_emoji("✅", premium)} Success', result['success']),
            (f'{_user_emoji("💀", premium)} Dead', result['dead']),
            (f'{_user_emoji("⚠️", premium)} Error', result['error']),
            (f'{_user_emoji("⏱", premium)} Time', f"{seconds}s"),
        ], raw=True),
        '</details>',
        '<details><summary><b>TODAY • THIS ACCOUNT ONLY</b></summary>',
        rich_table(["Metric", "Count"], [
            (f'{_user_emoji("📊", premium)} Total', stats.get('total', 0)),
            (f'{_user_emoji("✅", premium)} Success', stats.get('success', 0)),
            (f'{_user_emoji("💀", premium)} Dead', stats.get('dead', 0)),
            (f'{_user_emoji("⚠️", premium)} Error', stats.get('error', 0)),
        ], raw=True),
        '</details>',
        f'{_user_emoji("🔒", premium)} This report is scoped to <b>{title}</b>; other channels/groups are not merged into this target report.\n',
        rich_button_row(
            rich_button("Stats", emoji="📊", data="cmd:stats", style="primary", premium=premium),
            rich_button("Help", emoji="❓", data="cmd:help", style="primary", premium=premium),
        ),
    ])


def build_progress_html(attempted, success, dead, error, elapsed, premium=True):
    return "".join([
        f'<b>{_user_emoji("⚡", premium)} <b>PROCESSING JOIN REQUESTS</b></b>\n',
        rich_table(["Metric", "Live"], [
            (f'{_user_emoji("📨", premium)} Attempted', attempted),
            (f'{_user_emoji("✅", premium)} Success', success),
            (f'{_user_emoji("💀", premium)} Dead', dead),
            (f'{_user_emoji("⚠️", premium)} Error', error),
            (f'{_user_emoji("⏱", premium)} Elapsed', f"{elapsed}s"),
        ], raw=True),
    ])


def _fallback_action(premium, title, body):
    r = RichText(premium)
    r.line(f"🚀 {title}", MessageEntityType.BOLD)
    r.line("")
    r.line(body)
    return r.build()


def _fallback_stats(stats, premium):
    r = RichText(premium)
    r.line("📊 Today's Join Request Stats", MessageEntityType.BOLD)
    r.line("")
    r.line(f"📨 Total: {stats.get('total', 0)}")
    r.line(f"✅ Success: {stats.get('success', 0)}")
    r.line(f"💀 Dead: {stats.get('dead', 0)}")
    r.line(f"⚠️ Error: {stats.get('error', 0)}")
    return r.build()


@Client.on_message(filters.command("start") & filters.private)
async def start_message(c, m):
    if await db.is_banned(m.from_user.id):
        return await m.reply_text("<b>🚫 Your access to this bot has been disabled by an admin.</b>")

    if not await db.is_user_exist(m.from_user.id):
        await db.add_user(m.from_user.id, m.from_user.first_name)
        try:
            await c.send_message(LOG_CHANNEL, LOG_TEXT.format(m.from_user.id, m.from_user.mention))
        except Exception:
            pass
    else:
        await db.touch_user(m.from_user.id, m.from_user.first_name)

    enabled = await premium_enabled(db)
    html = build_start_html(m.from_user.first_name or "there", c.username, enabled)
    fallback = RichText(enabled)
    fallback.line("💎 SYNAX JOIN REQUEST HUB", MessageEntityType.BOLD)
    fallback.line("")
    fallback.line(f"👋 Welcome {m.from_user.first_name or 'there'}!")
    fallback.line("Open Help for Login, Accept and Stats.")
    await safe_send_rich(c, m.chat.id, html, fallback=fallback.build(), reply_markup=start_keyboard(c.username))



async def approve_pending_requests(acc, chat_id, owner_id, chat_title, status_msg, bot_client):
    result = {"attempted": 0, "success": 0, "dead": 0, "error": 0}
    started = time.monotonic()

    while True:
        requests = [r async for r in acc.get_chat_join_requests(chat_id, limit=100)]
        if not requests:
            break

        for req in requests:
            result["attempted"] += 1
            try:
                await acc.approve_chat_join_request(chat_id, req.user.id)
                result["success"] += 1
                await db.record_accept(owner_id, "success", chat_id, chat_title)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                try:
                    await acc.approve_chat_join_request(chat_id, req.user.id)
                    result["success"] += 1
                    await db.record_accept(owner_id, "success", chat_id, chat_title)
                except Exception:
                    result["error"] += 1
                    await db.record_accept(owner_id, "error", chat_id, chat_title)
            except (UserNotParticipant, RPCError):
                result["dead"] += 1
                await db.record_accept(owner_id, "dead", chat_id, chat_title)
            except Exception as exc:
                logging.warning("Join request approval failed for %s: %s", req.user.id, exc)
                result["error"] += 1
                await db.record_accept(owner_id, "error", chat_id, chat_title)

            if result["attempted"] % 20 == 0:
                elapsed = int(time.monotonic() - started)
                enabled = await premium_enabled(db)
                try:
                    await safe_edit_rich(
                        bot_client,
                        status_msg.chat.id,
                        status_msg.id,
                        build_progress_html(result["attempted"], result["success"], result["dead"], result["error"], elapsed, enabled),
                        fallback=RichText(enabled).line(f"⚡ Processing... {result['attempted']} attempted").build(),
                    )
                except Exception:
                    # status_msg may be a normal Pyrogram message; retain the
                    # original edit path as the guaranteed fallback.
                    try:
                        await status_msg.edit_text(
                            "<b>⚡ Processing join requests...</b>\n\n"
                            f"📨 Attempted: <code>{result['attempted']}</code>\n"
                            f"✅ Success: <code>{result['success']}</code>\n"
                            f"💀 Dead: <code>{result['dead']}</code>\n"
                            f"⚠️ Error: <code>{result['error']}</code>\n"
                            f"⏱ Time: <code>{elapsed}s</code>"
                        )
                    except Exception:
                        pass
    return result, int(time.monotonic() - started)


@Client.on_message(filters.command("accept") & filters.private)
async def accept(client, message):
    if await db.is_banned(message.from_user.id):
        return await message.reply_text("<b>🚫 Your access to this bot has been disabled by an admin.</b>")
    show = await message.reply_text("<b>⏳ Please wait...</b>")
    await db.touch_user(message.from_user.id, message.from_user.first_name)
    user_data = await db.get_session(message.from_user.id)
    if user_data is None:
        await show.edit_text("<b>❌ Please /login first to accept pending requests.</b>")
        return

    acc = Client(
        f"joinrequest_{message.from_user.id}",
        session_string=user_data,
        api_hash=API_HASH,
        api_id=API_ID,
        in_memory=True,
    )
    try:
        await acc.connect()
    except Exception:
        await show.edit_text("<b>❌ Your login session expired. Use /logout and then /login again.</b>")
        return

    try:
        enabled = await premium_enabled(db)
        await show.edit_text(
            "<b>📩 Forward a message from your channel or group.</b>\n\n"
            "Make sure the logged-in account is an admin there with permission to manage join requests."
        )
        vj = await client.listen(message.chat.id, timeout=300)
        if not vj.forward_from_chat or vj.forward_from_chat.type in [enums.ChatType.PRIVATE, enums.ChatType.BOT]:
            await show.edit_text("<b>❌ Message was not forwarded from a channel/group.</b>")
            return

        chat_id = vj.forward_from_chat.id
        try:
            info = await acc.get_chat(chat_id)
        except Exception:
            await show.edit_text("<b>❌ The logged-in account is not an admin or cannot access this channel/group.</b>")
            return

        try:
            await vj.delete()
        except Exception:
            pass

        chat_title = info.title or "Unknown Chat"
        chat_type = "Channel" if info.type == enums.ChatType.CHANNEL else "Group"
        await show.edit_text(f"<b>🚀 Starting...</b>\n\nChat: <b>{escape(chat_title)}</b>\nType: <b>{chat_type}</b>")

        result, seconds = await approve_pending_requests(acc, chat_id, message.from_user.id, chat_title, show, client)
        stats = await db.get_user_stats(message.from_user.id)
        enabled = await premium_enabled(db)
        report = build_accept_report_html(result, seconds, chat_title, chat_type, stats, enabled)

        # Replace the progress message with the rich final report when possible.
        try:
            await safe_edit_rich(client, message.chat.id, show.id, report, fallback=None)
        except Exception:
            fallback = RichText(enabled)
            fallback.line("🎉 ACCEPT COMPLETE", MessageEntityType.BOLD)
            fallback.line("")
            fallback.line(f"📣 Target: {chat_title}")
            fallback.line(f"📨 Attempted: {result['attempted']}")
            fallback.line(f"✅ Success: {result['success']}")
            fallback.line(f"💀 Dead: {result['dead']}")
            fallback.line(f"⚠️ Error: {result['error']}")
            fallback.line(f"⏱ Time: {seconds}s")
            await show.edit_text(fallback.build()[0], entities=fallback.build()[1], reply_markup=start_keyboard(client.username))

        # Individual target report: one DM for the selected channel/group only.
        try:
            await safe_send_rich(client, message.from_user.id, report)
        except Exception:
            pass
    except asyncio.TimeoutError:
        await show.edit_text("<b>⌛ Timed out. Send /accept again when you are ready.</b>")
    except Exception as e:
        logging.exception("accept failed")
        try:
            await show.edit_text(f"<b>❌ Error:</b> <code>{escape(str(e)[:700])}</code>")
        except Exception:
            pass
    finally:
        try:
            await acc.disconnect()
        except Exception:
            pass


@Client.on_message(filters.command("mystats") & filters.private)
async def my_stats(client, message):
    if await db.is_banned(message.from_user.id):
        return await message.reply_text("<b>🚫 Your access to this bot has been disabled by an admin.</b>")
    stats = await db.get_user_stats(message.from_user.id)
    enabled = await premium_enabled(db)
    await safe_send_rich(client, message.from_user.id, build_stats_html(stats, premium=enabled), fallback=_fallback_stats(stats, enabled))


@Client.on_chat_join_request(filters.group | filters.channel)
async def approve_new(client, m):
    if not NEW_REQ_MODE:
        return
    try:
        await client.approve_chat_join_request(m.chat.id, m.from_user.id)
        try:
            await client.send_message(
                m.from_user.id,
                f"<b>✅ Your join request for {escape(m.chat.title or 'the chat')} was accepted.</b>\n\nPowered By @SynaxBotz",
            )
        except Exception:
            pass
    except Exception as e:
        logging.warning("Auto approval failed: %s", e)
