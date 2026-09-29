# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

from pyrogram.types import Message
from pyrogram import Client, filters
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
)

from config import API_ID, API_HASH
from plugins.database import db
from plugins.rich import RichText, premium_enabled
from plugins.rich_api import safe_send_rich, rich_button, rich_button_row, tg_emoji

SESSION_STRING_SIZE = 351


def login_html(title, body, premium=True, action=None):
    icon = "🔐" if action != "otp" else "🔢"
    parts = [
        f'<b>{tg_emoji(icon, premium=premium)} <b>{title}</b></b>\n',
        f'{body}\n',
    ]
    if action == "phone":
        parts.append('<details open><summary><b>FORMAT</b></summary>Example: <code>+9171828181889</code>\n</details>')
    elif action == "otp":
        parts.append('<details open><summary><b>OTP FORMAT</b></summary>If OTP is <code>12345</code>, send <code>1 2 3 4 5</code>.\n</details>')
    elif action == "password":
        parts.append('<b>2-Step Verification</b> is enabled on this account.\n')
    parts.append(rich_button_row(rich_button("Cancel", emoji="❌", kind="callback_data", data="login:cancel", style="danger", premium=premium)))
    return "".join(parts)


async def wait_for_reply(bot, user_id, timeout):
    return await bot.listen(user_id, timeout=timeout)


@Client.on_message(filters.private & filters.command(["logout"]))
async def logout(client, message: Message):
    user_data = await db.get_session(message.from_user.id)
    if user_data is None:
        return
    await db.set_session(message.from_user.id, session=None)
    enabled = await premium_enabled(db)
    html = login_html("LOGOUT SUCCESS", "Your saved Telegram session has been removed from the bot.", enabled)
    fallback = RichText(enabled).line("🔓 LOGOUT SUCCESS", None).build()
    await safe_send_rich(client, message.chat.id, html, fallback=fallback)


@Client.on_message(filters.private & filters.command(["login"]))
async def main(bot: Client, message: Message):
    user_data = await db.get_session(message.from_user.id)
    enabled = await premium_enabled(db)
    if user_data is not None:
        html = login_html("ALREADY LOGGED IN", "Use /logout first, then start /login again.", enabled)
        await safe_send_rich(bot, message.chat.id, html, fallback=RichText(enabled).line("🔐 Already logged in", None).build())
        return

    user_id = int(message.from_user.id)
    try:
        await safe_send_rich(
            bot,
            user_id,
            login_html("SECURE LOGIN", "Send the phone number of the Telegram account you want to connect.", enabled, "phone"),
            fallback=RichText(enabled).line("🔐 Send phone number with country code.").build(),
        )
        phone_number_msg = await wait_for_reply(bot, user_id, 600)
        if not phone_number_msg.text:
            return
        if phone_number_msg.text.strip().lower() == "/cancel":
            await safe_send_rich(bot, user_id, login_html("CANCELLED", "Login process cancelled.", enabled), fallback=RichText(enabled).line("❌ Login cancelled.").build())
            return
        phone_number = phone_number_msg.text.strip()

        client = Client(":memory:", API_ID, API_HASH)
        await client.connect()
        try:
            await safe_send_rich(bot, user_id, login_html("SENDING OTP", "Telegram is sending a login code to your official Telegram account.", enabled), fallback=RichText(enabled).line("📨 Sending OTP...").build())
            code = await client.send_code(phone_number)
            await safe_send_rich(
                bot,
                user_id,
                login_html("ENTER OTP", "Check your official Telegram app and send the received OTP.", enabled, "otp"),
                fallback=RichText(enabled).line("🔢 Enter OTP as spaced digits.").build(),
            )
            phone_code_msg = await wait_for_reply(bot, user_id, 600)
            if not phone_code_msg.text:
                return
            if phone_code_msg.text.strip().lower() == "/cancel":
                await safe_send_rich(bot, user_id, login_html("CANCELLED", "Login process cancelled.", enabled), fallback=RichText(enabled).line("❌ Login cancelled.").build())
                return
            phone_code = phone_code_msg.text.replace(" ", "").strip()
            try:
                await client.sign_in(phone_number, code.phone_code_hash, phone_code)
            except SessionPasswordNeeded:
                await safe_send_rich(
                    bot,
                    user_id,
                    login_html("2-STEP VERIFICATION", "Your Telegram account requires its 2-step verification password.", enabled, "password"),
                    fallback=RichText(enabled).line("🔒 Enter your 2-step verification password.").build(),
                )
                two_step_msg = await wait_for_reply(bot, user_id, 300)
                if not two_step_msg.text:
                    return
                if two_step_msg.text.strip().lower() == "/cancel":
                    await safe_send_rich(bot, user_id, login_html("CANCELLED", "Login process cancelled.", enabled), fallback=RichText(enabled).line("❌ Login cancelled.").build())
                    return
                await client.check_password(password=two_step_msg.text)

            string_session = await client.export_session_string()
        finally:
            await client.disconnect()

        if len(string_session) < SESSION_STRING_SIZE:
            await safe_send_rich(bot, user_id, login_html("INVALID SESSION", "Telegram returned an invalid session string. Please try /login again.", enabled), fallback=RichText(enabled).line("❌ Invalid session string.").build())
            return

        try:
            existing = await db.get_session(user_id)
            if existing is None:
                uclient = Client(":memory:", session_string=string_session, api_id=API_ID, api_hash=API_HASH)
                await uclient.connect()
                await uclient.disconnect()
                await db.set_session(user_id, session=string_session)
        except Exception as e:
            await safe_send_rich(bot, user_id, login_html("LOGIN ERROR", str(e)[:700], enabled), fallback=RichText(enabled).line(f"❌ ERROR IN LOGIN: {e}").build())
            return

        html = "".join([
            f'<b>{tg_emoji("✅", premium=enabled)} <b>ACCOUNT LOGIN SUCCESS</b></b>\n',
            'Your Telegram account is connected successfully.\n',
            'If you get an AUTH KEY error later, use /logout and then /login again.\n',
            rich_button_row(
                rich_button("Accept", emoji="🚀", data="cmd:accept", style="success", premium=enabled),
                rich_button("Stats", emoji="📊", data="cmd:stats", style="link", premium=enabled),
                rich_button("Help", emoji="❓", data="cmd:help", style="primary", premium=enabled),
            ),
        ])
        await safe_send_rich(bot, user_id, html, fallback=RichText(enabled).line("✅ ACCOUNT LOGIN SUCCESS", None).build())
    except PhoneNumberInvalid:
        await safe_send_rich(bot, user_id, login_html("INVALID PHONE", "The phone number is invalid. Include the country code and try again.", enabled), fallback=RichText(enabled).line("❌ PHONE_NUMBER is invalid.").build())
    except PhoneCodeInvalid:
        await safe_send_rich(bot, user_id, login_html("INVALID OTP", "The OTP was not accepted. Start /login again for a fresh code.", enabled), fallback=RichText(enabled).line("❌ OTP is invalid.").build())
    except PhoneCodeExpired:
        await safe_send_rich(bot, user_id, login_html("OTP EXPIRED", "The OTP expired. Start /login again.", enabled), fallback=RichText(enabled).line("❌ OTP expired.").build())
    except PasswordHashInvalid:
        await safe_send_rich(bot, user_id, login_html("INVALID PASSWORD", "The 2-step verification password was not accepted.", enabled), fallback=RichText(enabled).line("❌ Invalid 2-step password.").build())
    except (ApiIdInvalid, Exception) as e:
        # Keep the last guard broad so a login failure never crashes the bot.
        await safe_send_rich(bot, user_id, login_html("LOGIN FAILED", str(e)[:700], enabled), fallback=RichText(enabled).line(f"❌ LOGIN FAILED: {e}").build())
