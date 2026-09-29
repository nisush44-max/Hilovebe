import datetime
import time
from html import escape

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import MessageEntityType

from config import ADMINS, NEW_REQ_MODE
from plugins.database import db
from plugins.rich import RichText, premium_enabled
from plugins.rich_api import safe_send_rich, safe_edit_rich, rich_button, rich_button_row, rich_table, tg_emoji

START_TIME = time.monotonic()
ADMIN_IDS = set(ADMINS if isinstance(ADMINS, (list, tuple, set)) else [ADMINS])


def is_admin(user_id):
    return int(user_id) in ADMIN_IDS


def fmt_uptime():
    seconds = int(time.monotonic() - START_TIME)
    d, seconds = divmod(seconds, 86400)
    h, seconds = divmod(seconds, 3600)
    m, s = divmod(seconds, 60)
    return f"{d}d {h}h {m}m {s}s"


def panel():
    # Fallback only. The normal admin UI is a native Rich Message.
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Overview", callback_data="adm:overview"), InlineKeyboardButton("📈 Today", callback_data="adm:today")],
        [InlineKeyboardButton("👥 Users", callback_data="adm:users"), InlineKeyboardButton("🔐 Sessions", callback_data="adm:sessions")],
        [InlineKeyboardButton("🏆 Top Users", callback_data="adm:top"), InlineKeyboardButton("📝 Recent Accepts", callback_data="adm:recent")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="adm:broadcast"), InlineKeyboardButton("📜 Broadcast History", callback_data="adm:broadcasts")],
        [InlineKeyboardButton("⚡ Auto Mode", callback_data="adm:automode"), InlineKeyboardButton("✨ Premium Emojis", callback_data="adm:premium")],
        [InlineKeyboardButton("🗄 DB Health", callback_data="adm:db"), InlineKeyboardButton("🧩 DB Collections", callback_data="adm:collections")],
        [InlineKeyboardButton("⏱ Uptime", callback_data="adm:uptime"), InlineKeyboardButton("ℹ️ Bot Info", callback_data="adm:info")],
        [InlineKeyboardButton("📅 7 Day", callback_data="adm:7day"), InlineKeyboardButton("📆 Yesterday", callback_data="adm:yesterday")],
        [InlineKeyboardButton("🗓 30 Day", callback_data="adm:30day"), InlineKeyboardButton("🔥 Active Users", callback_data="adm:active")],
        [InlineKeyboardButton("⚙️ Config", callback_data="adm:config"), InlineKeyboardButton("📚 Admin Help", callback_data="adm:help")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="adm:overview"), InlineKeyboardButton("❌ Close", callback_data="adm:close")],
    ])


def E(emoji, premium):
    return tg_emoji(emoji, premium=premium)


def admin_button(label, emoji, action, premium, style="primary"):
    return rich_button(label, emoji=emoji, data=f"adm:{action}", style=style, premium=premium)


def admin_panel_html(premium=True):
    s = "ON" if premium else "OFF"
    return "".join([
        f'<b>{E("🛠", premium)} <b>ADVANCED ADMIN CONTROL CENTER</b></b>\n',
        f'{E("✨", premium)} Premium custom emojis: <b>{s}</b> • {E("⚡", premium)} Auto mode: <b>{"ON" if NEW_REQ_MODE else "OFF"}</b> • {E("⏱", premium)} Uptime: <code>{fmt_uptime()}</code>\n',
        '<details open><summary><b>LIVE OVERVIEW</b></summary>',
        rich_table(["Metric", "Value"], [
            (f'{E("👥", premium)} Users', awaitable_placeholder("users")),
            (f'{E("🔐", premium)} Sessions', awaitable_placeholder("sessions")),
            (f'{E("📨", premium)} Today', awaitable_placeholder("today")),
        ], raw=True),
        '</details>',
        '<b>Management</b>\n',
        rich_button_row(admin_button("Overview", "📊", "overview", premium), admin_button("Today", "📈", "today", premium)),
        rich_button_row(admin_button("Users", "👥", "users", premium), admin_button("Sessions", "🔐", "sessions", premium)),
        rich_button_row(admin_button("Top Users", "🏆", "top", premium), admin_button("Recent Accepts", "📝", "recent", premium)),
        rich_button_row(admin_button("Broadcast", "📢", "broadcast", premium, "success"), admin_button("Broadcast History", "📜", "broadcasts", premium, "link")),
        rich_button_row(admin_button("Auto Mode", "⚡", "automode", premium), admin_button("Premium Emojis", "✨", "premium", premium, "success")),
        rich_button_row(admin_button("DB Health", "🗄", "db", premium), admin_button("Collections", "🧩", "collections", premium)),
        rich_button_row(admin_button("Uptime", "⏱", "uptime", premium), admin_button("Bot Info", "ℹ️", "info", premium)),
        rich_button_row(admin_button("7 Day", "📅", "7day", premium), admin_button("Yesterday", "📆", "yesterday", premium)),
        rich_button_row(admin_button("30 Day", "🗓", "30day", premium), admin_button("Active Users", "🔥", "active", premium)),
        rich_button_row(admin_button("Config", "⚙️", "config", premium), admin_button("Admin Help", "📚", "help", premium)),
        rich_button_row(admin_button("Refresh", "🔄", "overview", premium, "link"), admin_button("Close", "❌", "close", premium, "danger")),
    ])


def awaitable_placeholder(_):
    # The panel is rendered once immediately; detailed live values are shown
    # after pressing Overview/Today. Keeping the first card static avoids a
    # blocking DB round-trip just to draw the control grid.
    return "Tap Overview"


async def admin_rich(title, lines, premium=True):
    r = RichText(premium)
    r.line(f"{title}", style=None)
    r.line("")
    for line in lines:
        r.line(line)
    return r.build()


async def admin_detail_html(action, premium=True):
    if action in ("overview", "today"):
        s = await db.get_global_stats()
        return "".join([
            f'<b>{E("📊", premium)} <b>ADMIN OVERVIEW</b></b>\n',
            rich_table(["Metric", "Value"], [
                (f'{E("👥", premium)} Total Users', await db.total_users_count()),
                (f'{E("🔐", premium)} Logged-in', await db.active_sessions_count()),
                (f'{E("📨", premium)} Today Requests', s.get("total", 0)),
                (f'{E("✅", premium)} Success', s.get("success", 0)),
                (f'{E("💀", premium)} Dead', s.get("dead", 0)),
                (f'{E("⚠️", premium)} Errors', s.get("error", 0)),
                (f'{E("✨", premium)} Premium UI', "ON" if premium else "OFF"),
                (f'{E("⚡", premium)} Auto Approval', "ON" if NEW_REQ_MODE else "OFF"),
                (f'{E("⏱", premium)} Uptime', fmt_uptime()),
            ], raw=True),
        ])
    if action == "users":
        users = await db.get_recent_users(10)
        rows = [(u.get("id"), u.get("name", "Unknown")) for u in users]
        return f'<b>{E("👥", premium)} <b>RECENT USERS</b></b>\n' + rich_table(["User ID", "Name"], rows, raw=False)
    if action == "sessions":
        return f'<b>{E("🔐", premium)} <b>SESSIONS</b></b>\nConnected Telegram accounts: <b>{await db.active_sessions_count()}</b>\n'
    if action == "top":
        rows = await db.get_top_users(limit=10)
        table = [(i, r.get("user_id"), r.get("success", 0), r.get("dead", 0), r.get("error", 0)) for i, r in enumerate(rows, 1)]
        return f'<b>{E("🏆", premium)} <b>TOP USERS</b></b>\n' + rich_table(["#", "User", "Success", "Dead", "Error"], table)
    if action == "recent":
        rows = await db.get_recent_accepts(12)
        table = [(r.get("user_id"), r.get("status"), r.get("chat_title") or "Unknown", r.get("amount", 1)) for r in rows]
        return f'<b>{E("📝", premium)} <b>RECENT ACCEPTS</b></b>\n' + rich_table(["User", "Status", "Target", "Amount"], table)
    if action == "broadcasts":
        rows = await db.get_broadcasts(10)
        table = [(r.get("started_at"), r.get("success", 0), r.get("blocked", 0), r.get("failed", 0)) for r in rows]
        return f'<b>{E("📜", premium)} <b>BROADCAST HISTORY</b></b>\n' + rich_table(["Started", "Success", "Blocked", "Failed"], table)
    if action == "broadcast":
        return "".join([
            f'<b>{E("📢", premium)} <b>BROADCAST CENTER</b></b>\n',
            '<details open><summary><b>WORKFLOW</b></summary>Reply to any message with <code>/broadcast</code> in this private admin chat. The bot records success, blocked, deleted and failed delivery counts.\n</details>',
        ])
    if action == "automode":
        return f'<b>{E("⚡", premium)} <b>AUTO JOIN REQUEST MODE</b></b>\nCurrent: <b>{"ON" if NEW_REQ_MODE else "OFF"}</b>\nControlled by <code>NEW_REQ_MODE</code> at startup.\n'
    if action == "premium":
        return "".join([
            f'<b>{E("✨", premium)} <b>PREMIUM EMOJI MODE</b></b>\n',
            f'Current: <b>{"ON" if premium else "OFF"}</b>\n',
            'ON uses the supplied custom emoji ID mapping in Rich Messages. OFF keeps only normal emoji fallbacks.\n',
            rich_button_row(rich_button(f"Premium Emojis: {'OFF' if premium else 'ON'}", emoji="✨", data="adm:toggle_premium", style="success", premium=premium)),
        ])
    if action == "db":
        try:
            await db.db_ping()
            return f'<b>{E("🗄", premium)} <b>DATABASE HEALTH</b></b>\n{E("✅", premium)} MongoDB ping successful.\n'
        except Exception as e:
            return f'<b>{E("🗄", premium)} <b>DATABASE HEALTH</b></b>\n{E("❌", premium)} <code>{escape(str(e)[:700])}</code>\n'
    if action == "uptime":
        return f'<b>{E("⏱", premium)} <b>BOT UPTIME</b></b>\n<code>{fmt_uptime()}</code>\n'
    if action == "info":
        return f'<b>{E("ℹ️", premium)} <b>BOT INFO</b></b>\nJoin Request Acceptor\nPyrofork + MongoDB\nTelegram Rich Messages + custom emojis\nAdmin tools + broadcast + per-user statistics\n'
    if action in ("7day", "30day"):
        days = 7 if action == "7day" else 30
        today = datetime.datetime.now(datetime.timezone.utc).date()
        total = success = dead = error = 0
        for i in range(days):
            day = (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            s = await db.get_global_stats(day)
            total += s.get("total", 0); success += s.get("success", 0); dead += s.get("dead", 0); error += s.get("error", 0)
        return f'<b>{E("📅", premium)} <b>LAST {days} DAYS</b></b>\n' + rich_table(["Metric", "Count"], [
            (f'{E("📨", premium)} Total', total), (f'{E("✅", premium)} Success', success),
            (f'{E("💀", premium)} Dead', dead), (f'{E("⚠️", premium)} Error', error)], raw=True)
    if action == "yesterday":
        day = (datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        s = await db.get_global_stats(day)
        return f'<b>{E("📆", premium)} <b>YESTERDAY • {day}</b></b>\n' + rich_table(["Metric", "Count"], [
            (f'{E("📨", premium)} Total', s.get("total", 0)), (f'{E("✅", premium)} Success', s.get("success", 0)),
            (f'{E("💀", premium)} Dead', s.get("dead", 0)), (f'{E("⚠️", premium)} Error', s.get("error", 0))], raw=True)
    if action == "active":
        now = datetime.datetime.now(datetime.timezone.utc)
        count = await db.col.count_documents({"last_seen": {"$gte": now - datetime.timedelta(days=1)}})
        return f'<b>{E("🔥", premium)} <b>ACTIVE USERS</b></b>\nUsers active in the last 24 hours: <b>{count}</b>\n'
    if action == "collections":
        names = await db.db.list_collection_names()
        return f'<b>{E("🧩", premium)} <b>MONGODB COLLECTIONS</b></b>\n' + rich_table(["Collection"], [(x,) for x in (names or ["No collections found."])])
    if action == "config":
        return f'<b>{E("⚙️", premium)} <b>CONFIG STATUS</b></b>\n' + rich_table(["Setting", "Status"], [
            ("Admin IDs", len(ADMIN_IDS)), ("NEW_REQ_MODE", "ON" if NEW_REQ_MODE else "OFF"),
            ("DB URI", "configured"), ("Bot Token", "configured"), ("Premium UI", "ON" if premium else "OFF")])
    return f'<b>{E("📚", premium)} <b>ADMIN HELP</b></b>\n<code>/admin</code> opens this panel.\n<code>/stats</code> shows global daily stats.\n<code>/broadcast</code> broadcasts a replied message.\n<code>/ban USER_ID</code> and <code>/unban USER_ID</code> manage bot-user access.\n'


def admin_nav_html(html, premium=True):
    return html + rich_button_row(
        admin_button("Back", "⬅️", "overview", premium, "link"),
        admin_button("Refresh", "🔄", "overview", premium, "primary"),
        admin_button("Close", "❌", "close", premium, "danger"),
    )


def fallback_text(action, premium=True):
    r = RichText(premium)
    r.line(action.upper(), MessageEntityType.BOLD)
    return r.build()


@Client.on_message(filters.command("admin") & filters.private & filters.user(ADMINS))
async def admin_command(client, message):
    enabled = await premium_enabled(db)
    fallback = RichText(enabled).line("🛠 Advanced Admin Panel", None).build()
    await safe_send_rich(client, message.chat.id, admin_panel_html(enabled), fallback=fallback, reply_markup=panel())


@Client.on_message(filters.command("stats") & filters.private & filters.user(ADMINS))
async def admin_stats(client, message):
    enabled = await premium_enabled(db)
    html = admin_nav_html(await admin_detail_html("overview", enabled), enabled)
    await safe_send_rich(client, message.chat.id, html, fallback=fallback_text("GLOBAL TODAY STATS", enabled), reply_markup=panel())


@Client.on_message(filters.command("ban") & filters.private & filters.user(ADMINS))
async def ban_user(client, message):
    if len(message.command) < 2 or not message.command[1].lstrip("-").isdigit():
        return await message.reply_text("Usage: <code>/ban USER_ID</code>")
    uid = int(message.command[1])
    await db.set_ban(uid, "Admin ban")
    await message.reply_text(f"<b>🚫 User banned:</b> <code>{uid}</code>")


@Client.on_message(filters.command("unban") & filters.private & filters.user(ADMINS))
async def unban_user(client, message):
    if len(message.command) < 2 or not message.command[1].lstrip("-").isdigit():
        return await message.reply_text("Usage: <code>/unban USER_ID</code>")
    uid = int(message.command[1])
    await db.remove_ban(uid)
    await message.reply_text(f"<b>✅ User unbanned:</b> <code>{uid}</code>")


