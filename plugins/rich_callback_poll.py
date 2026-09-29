"""Reliable Bot API callback router for Telegram Rich Messages.

Telegram's native Rich Message buttons are callback_query updates from the Bot API.
This module owns that transport so Rich buttons continue working even when the
Pyrogram MTProto layer does not expose the corresponding update.
"""
import asyncio
import json
import logging
from urllib.parse import quote

import aiohttp

from config import BOT_TOKEN, RICH_CALLBACK_POLL_TIMEOUT
from plugins.database import db
from plugins.rich import premium_enabled, RichText
from plugins.rich_api import send_rich_message, edit_rich_message, answer_callback, strip_custom_emoji_tags
from plugins.commands import build_help_html, build_stats_html, build_action_html, _fallback_stats, _fallback_action
from plugins.admin import admin_detail_html, admin_nav_html, admin_panel_html, is_admin

LOG = logging.getLogger(__name__)


class RichCallbackPoller:
    def __init__(self, bot):
        self.bot = bot
        self.offset = 0
        self.stop_event = asyncio.Event()
        self.task = None
        self._recent = {}

    async def _api(self, method, payload=None):
        if not BOT_TOKEN:
            raise RuntimeError("BOT_TOKEN is not configured")
        payload = payload or {}
        timeout = aiohttp.ClientTimeout(total=max(35, RICH_CALLBACK_POLL_TIMEOUT + 10))
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
                json=payload,
            ) as response:
                raw = await response.text()
                try:
                    data = json.loads(raw)
                except Exception:
                    raise RuntimeError(f"Bot API {method}: invalid JSON response")
                if not response.ok or not data.get("ok"):
                    raise RuntimeError(data.get("description", f"HTTP {response.status}"))
                return data.get("result")

    async def start(self):
        if not BOT_TOKEN:
            LOG.error("Rich callback poller disabled: BOT_TOKEN is missing")
            return
        self.stop_event.clear()
        try:
            # We use getUpdates only for callback_query. If a webhook is configured,
            # polling would conflict, so remove it without dropping pending updates.
            await self._api("deleteWebhook", {"drop_pending_updates": False})
        except Exception as exc:
            LOG.warning("Could not clear Bot API webhook before Rich polling: %s", exc)
        self.task = asyncio.create_task(self._loop(), name="rich-callback-poller")
        LOG.info("🟣 Native Rich callback poller started")

    async def stop(self):
        self.stop_event.set()
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        LOG.info("🟣 Native Rich callback poller stopped")

    def _claim(self, user_id, chat_id, message_id, data):
        now = asyncio.get_running_loop().time()
        self._recent = {k:v for k,v in self._recent.items() if now-v < 8}
        key=(int(user_id or 0), int(chat_id or 0), int(message_id or 0), str(data or ""))
        if key in self._recent:
            return False
        self._recent[key]=now
        if len(self._recent)>1024:
            self._recent=dict(list(self._recent.items())[-512:])
        return True

    async def _answer(self, qid, text=None, alert=False):
        try:
            await answer_callback(qid, text, alert)
        except Exception as exc:
            LOG.debug("answerCallbackQuery failed: %s", exc)

    async def _edit(self, chat_id, message_id, html):
        try:
            return await edit_rich_message(chat_id, message_id, html)
        except Exception:
            # If the rich endpoint rejects custom emoji, retry with normal emoji.
            return await edit_rich_message(chat_id, message_id, strip_custom_emoji_tags(html))

    async def _delete(self, chat_id, message_id):
        return await self._api("deleteMessage", {"chat_id": int(chat_id), "message_id": int(message_id)})

    async def _dispatch(self, q):
        user = q.get("from") or {}
        user_id = int(user.get("id") or 0)
        message = q.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        message_id = message.get("message_id")
        data = str(q.get("data") or "").strip()
        if not user_id or not data:
            return
        if not self._claim(user_id, chat_id, message_id, data):
            return
        if await db.is_banned(user_id):
            await self._answer(q.get("id"), "Access disabled.", True)
            return

        if data.startswith("cmd:"):
            action=data.split(":",1)[1]
            enabled=await premium_enabled(db)
            if action=="help":
                html=build_help_html(getattr(self.bot,"username",None), enabled)
                if chat_id and message_id:
                    await self._edit(chat_id,message_id,html)
                else:
                    await send_rich_message(user_id,html)
                await self._answer(q.get("id"))
            elif action=="stats":
                stats=await db.get_user_stats(user_id)
                html=build_stats_html(stats,premium=enabled)
                if chat_id and message_id:
                    await self._edit(chat_id,message_id,html)
                else:
                    await send_rich_message(user_id,html)
                await self._answer(q.get("id"))
            elif action=="login":
                html=build_action_html("LOGIN", "Use /login to securely connect the Telegram account that will manage join requests.", enabled)
                if chat_id and message_id: await self._edit(chat_id,message_id,html)
                else: await send_rich_message(user_id,html)
                await self._answer(q.get("id"),"Send /login in this chat.")
            elif action=="accept":
                html=build_action_html("ACCEPT REQUESTS", "Use /accept, then forward one message from the exact channel/group you want to process.", enabled)
                if chat_id and message_id: await self._edit(chat_id,message_id,html)
                else: await send_rich_message(user_id,html)
                await self._answer(q.get("id"),"Send /accept to start.")
            else:
                await self._answer(q.get("id"),"Unknown action.",True)
            return

        if data.startswith("adm:"):
            if not is_admin(user_id):
                await self._answer(q.get("id"),"Admin only.",True)
                return
            action=data.split(":",1)[1]
            if action=="close":
                if chat_id and message_id:
                    try: await self._delete(chat_id,message_id)
                    except Exception: pass
                await self._answer(q.get("id"))
                return
            if action=="toggle_premium":
                current=await premium_enabled(db)
                await db.set_setting("premium_emojis", not current)
                enabled=not current
                html=admin_nav_html(await admin_detail_html("premium",enabled),enabled)
            else:
                enabled=await premium_enabled(db)
                valid={"overview","today","users","sessions","top","recent","broadcast","broadcasts","automode","premium","db","uptime","info","7day","yesterday","30day","active","collections","config","help"}
                html=admin_nav_html(await admin_detail_html(action,enabled),enabled) if action in valid else admin_panel_html(enabled)
            if chat_id and message_id:
                try: await self._edit(chat_id,message_id,html)
                except Exception: await send_rich_message(user_id,html)
            else:
                await send_rich_message(user_id,html)
            await self._answer(q.get("id"))
            return

        await self._answer(q.get("id"),"Unsupported button.",True)

    async def _loop(self):
        while not self.stop_event.is_set():
            try:
                updates=await self._api("getUpdates", {
                    "offset": self.offset,
                    "timeout": RICH_CALLBACK_POLL_TIMEOUT,
                    "allowed_updates":["callback_query"],
                })
                for update in updates or []:
                    self.offset=max(self.offset,int(update.get("update_id",0))+1)
                    q=update.get("callback_query")
                    if q:
                        try: await self._dispatch(q)
                        except Exception: LOG.exception("Rich callback dispatch failed")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOG.warning("Rich callback polling error: %s", exc)
                try: await asyncio.wait_for(self.stop_event.wait(),timeout=2)
                except asyncio.TimeoutError: pass
