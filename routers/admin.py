import asyncio
import io
import logging
import aiohttp
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import CosmicBotz
from utils.fsm import fsm
import config as cfg

logger = logging.getLogger(__name__)
router = Router()


# ── Auth ──────────────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in cfg.ADMIN_IDS


# ── In-memory log buffer ──────────────────────────────────────────────────────

class LogBuffer(logging.Handler):
    def __init__(self, maxlines: int = 500):
        super().__init__()
        self._lines: list[str] = []
        self._max   = maxlines

    def emit(self, record: logging.LogRecord):
        ts   = datetime.utcnow().strftime("%H:%M:%S")
        line = f"[{ts}] [{record.levelname}] {record.name}: {record.getMessage()}"
        self._lines.append(line)
        if len(self._lines) > self._max:
            self._lines.pop(0)

    def get_text(self) -> str:
        return "\n".join(self._lines) if self._lines else "No logs yet."

    def clear(self):
        self._lines.clear()


_log_buffer = LogBuffer()
logging.getLogger().addHandler(_log_buffer)


# ── Keyboards ─────────────────────────────────────────────────────────────────

def admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Stats",      callback_data="adm_stats")
    kb.button(text="📢 Broadcast",  callback_data="adm_broadcast")
    kb.button(text="🌐 Mode",       callback_data="adm_mode")
    kb.button(text="📋 Logs",       callback_data="adm_log")
    kb.button(text="👥 Users",      callback_data="adm_users")
    kb.button(text="🔧 Maintenance",callback_data="adm_maintenance")
    kb.button(text="🔄 Update Bot", callback_data="adm_update")
    kb.button(text="❌ Close",       callback_data="adm_close")
    kb.adjust(2, 2, 2, 1, 1)
    return kb.as_markup()


def mode_kb(current: str):
    kb = InlineKeyboardBuilder()
    modes = [
        ("🟢 Public",      "public",      "Everyone can use the bot"),
        ("🔴 Private",     "private",     "Admin only"),
        ("🟡 Maintenance", "maintenance", "Shows maintenance message"),
        ("🔵 Beta",        "beta",        "Premium users only"),
        ("🟠 Readonly",    "readonly",    "No posting, browsing only"),
    ]
    for label, val, _ in modes:
        tick = " ✅" if current == val else ""
        kb.button(text=f"{label}{tick}", callback_data=f"adm_setmode_{val}")
    kb.button(text="🔙 Back", callback_data="adm_back")
    kb.adjust(1)
    return kb.as_markup()


def log_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Send as Message", callback_data="adm_log_text")
    kb.button(text="📄 Send as .txt File", callback_data="adm_log_file")
    kb.button(text="🗑 Clear Logs",       callback_data="adm_log_clear")
    kb.button(text="🔙 Back",             callback_data="adm_back")
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def users_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔍 User Info",      callback_data="adm_userinfo_prompt")
    kb.button(text="⛔ Ban User",       callback_data="adm_ban_prompt")
    kb.button(text="✅ Unban User",     callback_data="adm_unban_prompt")
    kb.button(text="⭐ Add Premium",    callback_data="adm_premium_prompt")
    kb.button(text="❌ Revoke Premium", callback_data="adm_revoke_prompt")
    kb.button(text="🔙 Back",           callback_data="adm_back")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()


def maintenance_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✉️ Set Maintenance Msg", callback_data="adm_set_maint_msg")
    kb.button(text="🔙 Back",                callback_data="adm_back")
    kb.adjust(1)
    return kb.as_markup()


# ── Mode guard (used in content.py / start.py) ────────────────────────────────

async def check_mode(user_id: int, bot=None) -> tuple[bool, str]:
    """
    Returns (allowed: bool, reason: str).
    Call this at the top of user-facing handlers.
    """
    if is_admin(user_id):
        return True, ""

    mode = await CosmicBotz.get_bot_mode()

    if mode == "public":
        return True, ""

    if mode == "private":
        return False, "🔒 <b>Bot is in private mode.</b>\nOnly admins can use it right now."

    if mode == "maintenance":
        msg = await CosmicBotz.get_maintenance_message()
        return False, msg or "🔧 <b>Bot is under maintenance.</b>\nPlease check back soon."

    if mode == "beta":
        user = await CosmicBotz.get_user(user_id)
        if user and user.get("is_premium"):
            return True, ""
        return False, "🔵 <b>Bot is in Beta mode.</b>\nOnly ⭐ Premium users have access right now."

    if mode == "readonly":
        return True, ""   # readonly is checked per-action, not at entry

    return True, ""


# ── Commands ──────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    tu   = await CosmicBotz.total_users()
    tp   = await CosmicBotz.total_posts()
    mode = await CosmicBotz.get_bot_mode()
    await message.answer(
        f"👑 <b>Admin Panel</b>\n\n"
        f"👥 Users:  <b>{tu}</b>\n"
        f"📤 Posts:  <b>{tp}</b>\n"
        f"🌐 Mode:   <code>{mode}</code>",
        reply_markup=admin_kb(),
    )


@router.message(Command("mode"))
async def cmd_mode(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    valid = ("public", "private", "maintenance", "beta", "readonly")
    if not args or args[0] not in valid:
        current = await CosmicBotz.get_bot_mode()
        await message.answer(
            f"🌐 <b>Bot Mode</b>\n\nCurrent: <code>{current}</code>\n\n"
            f"Usage: <code>/mode [{'|'.join(valid)}]</code>",
            reply_markup=mode_kb(current),
        )
        return
    new_mode = args[0]
    await CosmicBotz.set_bot_mode(new_mode)
    await message.answer(f"✅ Mode set to <code>{new_mode}</code>.")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return
    await fsm.set(message.from_user.id, {"step": "adm_broadcast"})
    await message.answer("📢 Send the message to broadcast to all users:")


@router.message(Command("log"))
async def cmd_log(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("📋 <b>Logs</b>\n\nHow do you want to receive the logs?", reply_markup=log_kb())


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args or not args[0].isdigit():
        await message.answer("Usage: /ban <code>user_id</code>")
        return
    uid = int(args[0])
    await CosmicBotz.ban_user(uid)
    await message.answer(f"⛔ User <code>{uid}</code> banned.")
    try:
        await message.bot.send_message(uid, "⛔ You have been <b>banned</b> from this bot.")
    except Exception:
        pass


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args or not args[0].isdigit():
        await message.answer("Usage: /unban <code>user_id</code>")
        return
    uid = int(args[0])
    await CosmicBotz.unban_user(uid)
    await message.answer(f"✅ User <code>{uid}</code> unbanned.")
    try:
        await message.bot.send_message(uid, "✅ You have been <b>unbanned</b>. Welcome back!")
    except Exception:
        pass


@router.message(Command("addpremium"))
async def cmd_addpremium(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args or not args[0].isdigit():
        await message.answer("Usage: /addpremium <code>user_id</code>")
        return
    uid = int(args[0])
    await CosmicBotz.set_premium(uid, True)
    await message.answer(f"⭐ <code>{uid}</code> upgraded to Premium.")
    try:
        await message.bot.send_message(uid, "🎉 <b>You've been upgraded to ⭐ Premium!</b>\nEnjoy unlimited access.")
    except Exception:
        pass


@router.message(Command("revokepremium"))
async def cmd_revokepremium(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args or not args[0].isdigit():
        await message.answer("Usage: /revokepremium <code>user_id</code>")
        return
    uid = int(args[0])
    await CosmicBotz.set_premium(uid, False)
    await message.answer(f"✅ Premium revoked for <code>{uid}</code>.")
    try:
        await message.bot.send_message(uid, "ℹ️ Your <b>Premium</b> access has been revoked.")
    except Exception:
        pass


@router.message(Command("userinfo"))
async def cmd_userinfo(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args or not args[0].lstrip("-").isdigit():
        await message.answer("Usage: /userinfo <code>user_id</code>")
        return
    await _send_userinfo(message, int(args[0]))


@router.message(Command("globalstats"))
async def cmd_globalstats(message: Message):
    if not is_admin(message.from_user.id):
        return
    await _send_stats(message)


@router.message(Command("maintenance"))
async def cmd_maintenance(message: Message):
    """Shortcut: /maintenance <message text> — sets mode to maintenance + saves msg."""
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        await message.answer(
            "Usage: <code>/maintenance Your maintenance message here</code>\n\n"
            "This sets the bot to maintenance mode and saves the message shown to users."
        )
        return
    text = parts[1].strip()
    await CosmicBotz.set_bot_mode("maintenance")
    await CosmicBotz.set_maintenance_message(text)
    await message.answer(
        f"🔧 <b>Maintenance mode ON</b>\n\n"
        f"Message shown to users:\n<i>{text}</i>\n\n"
        f"Use <code>/mode public</code> to bring the bot back online."
    )


@router.message(Command("update"))
async def cmd_update(message: Message):
    """Trigger a redeploy from latest Git commit on Render."""
    if not is_admin(message.from_user.id):
        return
    await _trigger_render_deploy(message)


# ── Render deploy helper ──────────────────────────────────────────────────────

async def _trigger_render_deploy(target: Message):
    """POST to Render deploy hook and report result to target message."""
    hook = getattr(cfg, "RENDER_DEPLOY_HOOK", "")
    if not hook:
        await target.answer(
            "❌ <b>RENDER_DEPLOY_HOOK</b> is not set.\n\n"
            "Add it to your <code>.env</code> and <code>config.py</code>:\n"
            "<code>RENDER_DEPLOY_HOOK=https://api.render.com/deploy/srv-xxx?key=yyy</code>"
        )
        return
    msg = await target.answer("🔄 <b>Triggering deploy on Render...</b>")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(hook, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status in (200, 201):
                    await msg.edit_text(
                        "✅ <b>Deploy triggered!</b>\n\n"
                        "⏳ Render is pulling the latest commit and restarting.\n"
                        "<i>The bot will go offline briefly during the restart.</i>"
                    )
                else:
                    body = await resp.text()
                    await msg.edit_text(
                        f"⚠️ <b>Render responded with HTTP {resp.status}</b>\n\n"
                        f"<code>{body[:300]}</code>"
                    )
    except aiohttp.ClientError as e:
        await msg.edit_text(f"❌ <b>Request failed:</b> <code>{e}</code>")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _send_stats(target: Message):
    tu   = await CosmicBotz.total_users()
    tp   = await CosmicBotz.total_posts()
    mode = await CosmicBotz.get_bot_mode()
    pu   = await CosmicBotz.total_premium_users()
    bu   = await CosmicBotz.total_banned_users()
    # Active today
    active = await CosmicBotz.active_users_today()
    text = (
        f"📊 <b>Global Stats</b>\n\n"
        f"👥 Total Users:   <b>{tu}</b>\n"
        f"🟢 Active Today:  <b>{active}</b>\n"
        f"⭐ Premium:       <b>{pu}</b>\n"
        f"⛔ Banned:        <b>{bu}</b>\n"
        f"📤 Total Posts:   <b>{tp}</b>\n"
        f"🌐 Bot Mode:      <code>{mode}</code>"
    )
    if isinstance(target, Message):
        await target.answer(text, reply_markup=admin_kb())
    else:
        await target.edit_text(text, reply_markup=admin_kb())


async def _send_userinfo(target: Message, uid: int):
    user = await CosmicBotz.get_user(uid)
    if not user:
        await target.answer("❌ User not found in DB.")
        return
    s        = user.get("settings", {})
    joined   = user.get("joined", "?")
    last     = user.get("last_seen", "?")
    if isinstance(joined, datetime):
        joined = joined.strftime("%Y-%m-%d")
    if isinstance(last, datetime):
        last = last.strftime("%Y-%m-%d %H:%M")
    await target.answer(
        f"👤 <b>User Info</b>\n\n"
        f"ID:         <code>{uid}</code>\n"
        f"Name:       {user.get('full_name', 'N/A')}\n"
        f"Username:   @{user.get('username', 'N/A')}\n"
        f"Joined:     <code>{joined}</code>\n"
        f"Last Seen:  <code>{last}</code>\n"
        f"Posts:      <b>{user.get('post_count', 0)}</b>\n"
        f"Premium:    {'⭐ Yes' if user.get('is_premium') else 'No'}\n"
        f"Banned:     {'⛔ Yes' if user.get('is_banned') else 'No'}\n"
        f"Channel:    <code>{s.get('channel_id') or 'Not set'}</code>\n"
        f"Watermark:  <code>{s.get('watermark') or 'Not set'}</code>\n"
        f"Template:   <code>{s.get('active_template', 'default')}</code>"
    )


# ── Broadcast ─────────────────────────────────────────────────────────────────

async def do_broadcast(message: Message, text: str):
    """Called from content.py handle_text_input when step=adm_broadcast."""
    await fsm.clear(message.from_user.id)
    user_ids = await CosmicBotz.get_all_user_ids()
    status   = await message.answer(f"📤 Broadcasting to <b>{len(user_ids)}</b> users...")
    ok = fail = 0
    for uid in user_ids:
        try:
            await message.bot.send_message(uid, f"📢 <b>Announcement</b>\n\n{text}")
            ok += 1
        except Exception:
            fail += 1
        if ok % 25 == 0:
            await asyncio.sleep(1)
    await status.edit_text(
        f"✅ Broadcast done!\n"
        f"✔ Sent: <b>{ok}</b>   ✘ Failed: <b>{fail}</b>"
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_"))
async def adm_callback(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔ Admin only.", show_alert=True)
        return
    await cb.answer()
    uid  = cb.from_user.id
    data = cb.data

    # ── Navigation ────────────────────────────────────────────────────────────

    if data == "adm_back":
        tu   = await CosmicBotz.total_users()
        tp   = await CosmicBotz.total_posts()
        mode = await CosmicBotz.get_bot_mode()
        await cb.message.edit_text(
            f"👑 <b>Admin Panel</b>\n\n"
            f"👥 Users: <b>{tu}</b>\n"
            f"📤 Posts: <b>{tp}</b>\n"
            f"🌐 Mode:  <code>{mode}</code>",
            reply_markup=admin_kb(),
        )

    elif data == "adm_close":
        try:
            await cb.message.delete()
        except Exception:
            pass

    # ── Stats ─────────────────────────────────────────────────────────────────

    elif data == "adm_stats":
        tu     = await CosmicBotz.total_users()
        tp     = await CosmicBotz.total_posts()
        mode   = await CosmicBotz.get_bot_mode()
        pu     = await CosmicBotz.total_premium_users()
        bu     = await CosmicBotz.total_banned_users()
        active = await CosmicBotz.active_users_today()
        await cb.message.edit_text(
            f"📊 <b>Global Stats</b>\n\n"
            f"👥 Total Users:   <b>{tu}</b>\n"
            f"🟢 Active Today:  <b>{active}</b>\n"
            f"⭐ Premium:       <b>{pu}</b>\n"
            f"⛔ Banned:        <b>{bu}</b>\n"
            f"📤 Total Posts:   <b>{tp}</b>\n"
            f"🌐 Bot Mode:      <code>{mode}</code>",
            reply_markup=admin_kb(),
        )

    # ── Broadcast ─────────────────────────────────────────────────────────────

    elif data == "adm_broadcast":
        await fsm.set(uid, {"step": "adm_broadcast"})
        await cb.message.edit_text("📢 Send the broadcast message now:")

    # ── Mode ──────────────────────────────────────────────────────────────────

    elif data == "adm_mode":
        current = await CosmicBotz.get_bot_mode()
        await cb.message.edit_text(
            f"🌐 <b>Bot Mode</b>\n\nCurrent: <code>{current}</code>\n\n"
            "🟢 <b>Public</b> — everyone can use the bot\n"
            "🔴 <b>Private</b> — admin only\n"
            "🟡 <b>Maintenance</b> — shows maintenance message\n"
            "🔵 <b>Beta</b> — premium users only\n"
            "🟠 <b>Readonly</b> — browsing allowed, no posting",
            reply_markup=mode_kb(current),
        )

    elif data.startswith("adm_setmode_"):
        new_mode = data.replace("adm_setmode_", "")
        await CosmicBotz.set_bot_mode(new_mode)
        await cb.answer(f"✅ Mode → {new_mode}", show_alert=True)
        await cb.message.edit_text(
            f"🌐 <b>Bot Mode</b>\n\nCurrent: <code>{new_mode}</code>\n\n"
            "🟢 <b>Public</b> — everyone can use the bot\n"
            "🔴 <b>Private</b> — admin only\n"
            "🟡 <b>Maintenance</b> — shows maintenance message\n"
            "🔵 <b>Beta</b> — premium users only\n"
            "🟠 <b>Readonly</b> — browsing allowed, no posting",
            reply_markup=mode_kb(new_mode),
        )

    # ── Logs ──────────────────────────────────────────────────────────────────

    elif data == "adm_log":
        await cb.message.edit_text(
            "📋 <b>Logs</b>\n\nHow do you want to receive the logs?",
            reply_markup=log_kb(),
        )

    elif data == "adm_log_text":
        raw  = _log_buffer.get_text()
        # Escape < and > so Telegram HTML parser never chokes on tracebacks
        safe = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        tail = safe[-3800:] if len(safe) > 3800 else safe
        await cb.message.answer(
            f"📋 <b>Recent Logs</b>\n\n<pre>{tail}</pre>",
            reply_markup=log_kb(),
        )

    elif data == "adm_log_file":
        raw  = _log_buffer.get_text()
        name = f"logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
        buf  = io.BytesIO(raw.encode("utf-8"))
        await cb.message.answer_document(
            document=BufferedInputFile(buf.getvalue(), filename=name),
            caption="📄 Full log file",
        )

    elif data == "adm_log_clear":
        _log_buffer.clear()
        await cb.answer("🗑 Logs cleared.", show_alert=True)
        await cb.message.edit_text(
            "📋 <b>Logs</b>\n\nHow do you want to receive the logs?",
            reply_markup=log_kb(),
        )

    # ── Users panel ───────────────────────────────────────────────────────────

    elif data == "adm_users":
        await cb.message.edit_text(
            "👥 <b>User Management</b>\n\nChoose an action:",
            reply_markup=users_kb(),
        )

    elif data in (
        "adm_userinfo_prompt", "adm_ban_prompt", "adm_unban_prompt",
        "adm_premium_prompt", "adm_revoke_prompt",
    ):
        step_map = {
            "adm_userinfo_prompt": "adm_userinfo",
            "adm_ban_prompt":      "adm_ban",
            "adm_unban_prompt":    "adm_unban",
            "adm_premium_prompt":  "adm_addpremium",
            "adm_revoke_prompt":   "adm_revoke",
        }
        prompt_map = {
            "adm_userinfo_prompt": "🔍 Send the <b>user ID</b> to look up:",
            "adm_ban_prompt":      "⛔ Send the <b>user ID</b> to ban:",
            "adm_unban_prompt":    "✅ Send the <b>user ID</b> to unban:",
            "adm_premium_prompt":  "⭐ Send the <b>user ID</b> to grant Premium:",
            "adm_revoke_prompt":   "❌ Send the <b>user ID</b> to revoke Premium:",
        }
        await fsm.set(uid, {"step": step_map[data]})
        await cb.message.edit_text(prompt_map[data])

    # ── Maintenance message ───────────────────────────────────────────────────

    elif data == "adm_maintenance":
        current_msg = await CosmicBotz.get_maintenance_message()
        await cb.message.edit_text(
            f"🔧 <b>Maintenance Settings</b>\n\n"
            f"Current message:\n<i>{current_msg or 'Not set'}</i>",
            reply_markup=maintenance_kb(),
        )

    elif data == "adm_set_maint_msg":
        await fsm.set(uid, {"step": "adm_maint_msg"})
        await cb.message.edit_text(
            "🔧 Send the <b>maintenance message</b> users will see:\n\n"
            "<i>Example: We're upgrading the bot, back in 30 mins! 🚀</i>"
        )

    # ── Render deploy ─────────────────────────────────────────────────────────

    elif data == "adm_update":
        await _trigger_render_deploy(cb.message)