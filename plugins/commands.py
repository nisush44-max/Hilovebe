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


def _compact_quote(text):
    """Compact quote used for secondary/microcopy so the card stays clean."""
    return f"<blockquote><i>{escape(str(text))}</i></blockquote>"


def _section(title, body, open_=False):
    """Small Rich Message accordion section."""
    opened = " open" if open_ else ""
    return f"<details{opened}><summary><b>{escape(title)}</b></summary>{body}</details>"


def _footer(premium=True):
    return (
        f'{_user_emoji("✨", premium)} '
        f'<i>Powered by <b>Synax</b> • Fast · clean · secure</i>'
    )


def build_start_html(name, username, premium=True):
    n = escape(name or "there")
    title = f'{_user_emoji("💎", premium)} <b>SYNAX JOIN REQUEST HUB</b>'
    feature_rows = [
        (_user_emoji("⚡", premium), "<b>Fast approval</b>", "Process pending requests quickly"),
        (_user_emoji("🔗", premium), "<b>Channel + Group</b>", "Works with your selected target"),
        (_user_emoji("📊", premium), "<b>Live stats</b>", "See target and account results"),
        (_user_emoji("✨", premium), "<b>Rich interface</b>", "Native buttons, quotes & sections"),
    ]

    feature_body = rich_table(
        ["Feature", "Details"],
        [(f"{a} {b}", c) for a, b, c in feature_rows],
        raw=True,
    )

    flow_body = rich_table(
        ["", "Action"],
        [
            (f'{_user_emoji("01️⃣", premium)}', "Open Help"),
            (f'{_user_emoji("02️⃣", premium)}', "Login your Telegram account"),
            (f'{_user_emoji("03️⃣", premium)}', "Select one target chat"),
            (f'{_user_emoji("04️⃣", premium)}', "Accept requests + receive report"),
        ],
        raw=True,
    )

    return "".join([
        _slide_html(),
        f'{title}\n',
        f'<i>Fast · clean · secure join-request processing</i>\n\n',
        f'{_user_emoji("👋", premium)} <b>Welcome, {n}!</b>\n',
        _compact_quote(
            "Manage pending join requests from your own Telegram account. "
            "Choose one target, process it, and get a focused result report."
        ),
        _section("✦ LIVE FEATURES", feature_body, open_=True),
        "\n",
        _section("⌁ ACCOUNT FLOW", flow_body),
        "\n",
        _compact_quote("All main actions are inside the Rich Message controls below."),
        rich_button_row(*[
            rich_button("Help", emoji="❓", data="cmd:help", style="primary", premium=premium),
            rich_button("Shop", emoji="🤖", kind="url", url="https://t.me/ShopSynax", style="primary", premium=premium),
        ]),
        rich_button_row(*[
            rich_button("Update Channel", emoji="📢", kind="url", url="https://t.me/synaxbotz", style="success", premium=premium),
            rich_button("Support Group", emoji="💬", kind="url", url="https://t.me/synaxsupport", style="success", premium=premium),
        ]),
        rich_button_row(*[
            rich_button(
                "Add To Channel", emoji="➕", kind="url",
                url=f"https://t.me/{username.lstrip('@')}?startchannel=true",
                style="danger", premium=premium
            ),
            rich_button(
                "Add To Group", emoji="➕", kind="url",
                url=f"https://t.me/{username.lstrip('@')}?startgroup=true",
                style="danger", premium=premium
            ),
        ]),
        "\n",
        _footer(premium),
    ])


def build_help_html(username, premium=True):
    username = (username or "RequestApprovalBot").lstrip("@")

    how_body = rich_table(
        ["", "Do this"],
        [
            (f'{_user_emoji("01️⃣", premium)}', "Add the bot as admin to the target chat."),
            (f'{_user_emoji("02️⃣", premium)}', "Press Login and connect your Telegram account."),
            (f'{_user_emoji("03️⃣", premium)}', "Press Accept and forward one target message."),
            (f'{_user_emoji("04️⃣", premium)}', "The bot processes only that selected target."),
            (f'{_user_emoji("05️⃣", premium)}', "Receive that target's individual result report."),
        ],
        raw=True,
    )

    commands_body = rich_table(
        ["Command", "Purpose"],
        [
            ("/login", "Connect Telegram account"),
            ("/accept", "Process one selected target chat"),
            ("/mystats", "Show today's account stats"),
            ("/logout", "Remove saved session"),
        ],
    )

    return "".join([
        f'{_user_emoji("❓", premium)} <b>HELP • CONTROL CENTER</b>\n',
        '<i>Everything you need, kept short and easy to scan.</i>\n\n',
        _compact_quote("Use the buttons below for the main actions. No long command hunting."),
        _section("01 · HOW TO USE", how_body, open_=True),
        "\n",
        _section("02 · COMMANDS", commands_body),
        "\n",
        _section(
            "03 · RICH CONTROLS",
            _compact_quote(
                "Buttons use native Rich Message styling. "
                "Premium custom emojis are used when enabled."
            ),
            open_=True,
        ),
        "\n",
        rich_button_row(
            rich_button("Login", emoji="🔐", data="cmd:login", style="success", premium=premium),
            rich_button("Accept", emoji="🚀", data="cmd:accept", style="primary", premium=premium),
            rich_button("Stats", emoji="📊", data="cmd:stats", style="link", premium=premium),
        ),
        rich_button_row(
            rich_button(
                "Add To Channel", emoji="➕", kind="url",
                url=f"https://t.me/{username}?startchannel=true",
                style="success", premium=premium
            ),
            rich_button(
                "Add To Group", emoji="➕", kind="url",
                url=f"https://t.me/{username}?startgroup=true",
                style="success", premium=premium
            ),
        ),
        rich_button_row(
            rich_button("Support", emoji="💬", kind="url", url="https://t.me/SynaxSupport", style="danger", premium=premium),
            rich_button("Updates", emoji="📢", kind="url", url="https://t.me/SynaxBotz", style="danger", premium=premium),
        ),
        "\n",
        _footer(premium),
    ])


def build_action_html(title, body, premium=True):
    icon = "🚀" if "Accept" in title else "🔐" if "Login" in title else "⚙️"
    return "".join([
        f'{_user_emoji(icon, premium)} <b>{escape(title)}</b>\n',
        '<i>Action center</i>\n\n',
        _compact_quote(body),
        rich_button_row(
            rich_button("Help", emoji="❓", data="cmd:help", style="link", premium=premium),
            rich_button("Stats", emoji="📊", data="cmd:stats", style="link", premium=premium),
        ),
        "\n",
        _footer(premium),
    ])


def build_stats_html(stats, title="Today's Join Request Stats", premium=True):
    total = int(stats.get("total", 0))
    success = int(stats.get("success", 0))
    dead = int(stats.get("dead", 0))
    error = int(stats.get("error", 0))

    body = rich_table(
        ["Status", "Count"],
        [
            (f'{_user_emoji("📨", premium)} Total', total),
            (f'{_user_emoji("✅", premium)} Success', success),
            (f'{_user_emoji("💀", premium)} Dead', dead),
            (f'{_user_emoji("⚠️", premium)} Error', error),
        ],
        raw=True,
    )

    return "".join([
        f'{_user_emoji("📊", premium)} <b>{escape(title)}</b>\n',
        '<i>Today · this account only</i>\n\n',
        body,
        "\n",
        _compact_quote(
            "These numbers belong to your account. "
            "Target reports are kept separate from the overall account totals."
        ),
        _section(
            "ACCOUNT STATUS",
            _compact_quote(
                f"Rich UI: {'Premium custom emojis enabled' if premium else 'Normal emoji mode'}"
            ),
        ),
        "\n",
        rich_button_row(
            rich_button("Accept", emoji="🚀", data="cmd:accept", style="primary", premium=premium),
            rich_button("Help", emoji="❓", data="cmd:help", style="link", premium=premium),
        ),
        "\n",
        _footer(premium),
    ])


def build_accept_report_html(result, seconds, chat_title, chat_type, stats, premium=True):
    title = escape(chat_title or "Unknown Chat")

    target_body = rich_table(
        ["Metric", "Result"],
        [
            (f'{_user_emoji("📨", premium)} Attempted', result.get("attempted", 0)),
            (f'{_user_emoji("✅", premium)} Success', result.get("success", 0)),
            (f'{_user_emoji("💀", premium)} Dead', result.get("dead", 0)),
            (f'{_user_emoji("⚠️", premium)} Error', result.get("error", 0)),
            (f'{_user_emoji("⏱", premium)} Time', f"{seconds}s"),
        ],
        raw=True,
    )

    account_body = rich_table(
        ["Metric", "Count"],
        [
            (f'{_user_emoji("📊", premium)} Total', stats.get("total", 0)),
            (f'{_user_emoji("✅", premium)} Success', stats.get("success", 0)),
            (f'{_user_emoji("💀", premium)} Dead', stats.get("dead", 0)),
            (f'{_user_emoji("⚠️", premium)} Error', stats.get("error", 0)),
        ],
        raw=True,
    )

    return "".join([
        f'{_user_emoji("🎉", premium)} <b>ACCEPT COMPLETE</b>\n',
        f'<i>{_user_emoji("📣", premium)} Target result</i>\n\n',
        _compact_quote(f"{title} · {escape(chat_type)}"),
        _section("✦ TARGET RESULT", target_body, open_=True),
        "\n",
        _section("⌁ ACCOUNT TOTAL • TODAY", account_body),
        "\n",
        _compact_quote(
            f"This report is scoped to <b>{title}</b>. "
            "Other channels/groups are not merged into this target result."
        ),
        rich_button_row(
            rich_button("Stats", emoji="📊", data="cmd:stats", style="primary", premium=premium),
            rich_button("Accept Again", emoji="🚀", data="cmd:accept", style="link", premium=premium),
        ),
        "\n",
        _footer(premium),
    ])


def build_progress_html(attempted, success, dead, error, elapsed, premium=True):
    progress_body = rich_table(
        ["Metric", "Live"],
        [
            (f'{_user_emoji("📨", premium)} Attempted', attempted),
            (f'{_user_emoji("✅", premium)} Success', success),
            (f'{_user_emoji("💀", premium)} Dead', dead),
            (f'{_user_emoji("⚠️", premium)} Error', error),
            (f'{_user_emoji("⏱", premium)} Elapsed', f"{elapsed}s"),
        ],
        raw=True,
    )

    return "".join([
        f'{_user_emoji("⚡", premium)} <b>PROCESSING JOIN REQUESTS</b>\n',
        '<i>Live progress · selected target only</i>\n\n',
        _compact_quote("The counters below update while requests are being processed."),
        progress_body,
        "\n",
        _footer(premium),
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
