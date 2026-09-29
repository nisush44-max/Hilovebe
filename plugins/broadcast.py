from pyrogram.errors import InputUserDeactivated, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram import Client, filters
from config import ADMINS
from plugins.database import db
from plugins.rich import RichText, premium_enabled
from plugins.rich_api import safe_edit_rich, rich_table, tg_emoji
import asyncio
import datetime
import time
import logging

logger = logging.getLogger(__name__)


async def broadcast_messages(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        return False, "Deleted"
    except UserIsBlocked:
        await db.delete_user(int(user_id))
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        return False, "Deleted"
    except Exception:
        return False, "Error"


async def broadcast_html(total_users, done, success, blocked, deleted, failed, final=False, elapsed=None):
    enabled = await premium_enabled(db)
    title = "BROADCAST COMPLETE" if final else "BROADCAST IN PROGRESS"
    icon = "📢"
    rows = [
        (f'{tg_emoji("👥", premium=enabled)} Total', total_users),
        (f'{tg_emoji("📨", premium=enabled)} Completed', done),
        (f'{tg_emoji("✅", premium=enabled)} Success', success),
        (f'{tg_emoji("🚫", premium=enabled)} Blocked', blocked),
        (f'{tg_emoji("🗑", premium=enabled)} Deleted', deleted),
        (f'{tg_emoji("⚠️", premium=enabled)} Failed', failed),
    ]
    if elapsed is not None:
        rows.append((f'{tg_emoji("⏱", premium=enabled)} Time', elapsed))
    return f'<b>{tg_emoji(icon, premium=enabled)} <b>{title}</b></b>\n' + rich_table(["Metric", "Value"], rows, raw=True)


async def broadcast_fallback(total_users, done, success, blocked, deleted, failed, final=False, elapsed=None):
    enabled = await premium_enabled(db)
    r = RichText(enabled)
    r.line("📢 BROADCAST COMPLETE" if final else "📢 BROADCAST IN PROGRESS", None)
    r.line("")
    r.line(f"👥 Total: {total_users}")
    r.line(f"📨 Completed: {done}")
    r.line(f"✅ Success: {success}")
    r.line(f"🚫 Blocked: {blocked}")
    r.line(f"🗑 Deleted: {deleted}")
    r.line(f"⚠️ Failed: {failed}")
    if elapsed is not None:
        r.line(f"⏱ Time: {elapsed}")
    return r.build()


@Client.on_message(filters.command("broadcast") & filters.user(ADMINS) & filters.reply)
async def broadcast_command(bot, message):
    users = await db.get_all_users()
    b_msg = message.reply_to_message
    sts = await message.reply_text("<b>📢 Broadcast started...</b>")
    start_time = time.time()
    total_users = await db.total_users_count()
    done = success = blocked = deleted = failed = 0

    async for user in users:
        user_id = user.get("id")
        if not user_id:
            failed += 1
            continue
        ok, state = await broadcast_messages(int(user_id), b_msg)
        done += 1
        if ok:
            success += 1
        elif state == "Blocked":
            blocked += 1
        elif state == "Deleted":
            deleted += 1
        else:
            failed += 1

        if done % 20 == 0:
            html = await broadcast_html(total_users, done, success, blocked, deleted, failed)
            try:
                await safe_edit_rich(bot, sts.chat.id, sts.id, html, fallback=await broadcast_fallback(total_users, done, success, blocked, deleted, failed))
            except Exception:
                pass

    elapsed = datetime.timedelta(seconds=int(time.time() - start_time))
    data = {
        "started_at": datetime.datetime.fromtimestamp(start_time, datetime.timezone.utc),
        "completed_at": datetime.datetime.now(datetime.timezone.utc),
        "total": total_users,
        "completed": done,
        "success": success,
        "blocked": blocked,
        "deleted": deleted,
        "failed": failed,
        "seconds": int(time.time() - start_time),
        "admin_id": message.from_user.id,
    }
    await db.save_broadcast(data)
    html = await broadcast_html(total_users, done, success, blocked, deleted, failed, final=True, elapsed=elapsed)
    try:
        await safe_edit_rich(bot, sts.chat.id, sts.id, html, fallback=await broadcast_fallback(total_users, done, success, blocked, deleted, failed, final=True, elapsed=elapsed))
    except Exception:
        text, entities = await broadcast_fallback(total_users, done, success, blocked, deleted, failed, final=True, elapsed=elapsed)
        await message.reply_text(text, entities=entities)
