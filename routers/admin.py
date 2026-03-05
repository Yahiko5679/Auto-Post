import asyncio
import io
import logging
import aiohttp
from datetime import datetime, timedelta

from formatter.engine import sc
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import CosmicBotz
from utils.fsm import fsm
import config as cfg

logger = logging.getLogger(__name__)
router = Router()

# Tracks when the bot process started — used for uptime display
BOT_START_TIME: datetime = datetime.utcnow()


def _fmt_uptime() -> str:
    """Format uptime as  Xd HH:MM:SS  or  HH:MM:SS  if under 1 day."""
    delta    = datetime.utcnow() - BOT_START_TIME
    total_s  = int(delta.total_seconds())
    days, rem  = divmod(total_s, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours:02}:{mins:02}:{secs:02}"
    return f"{hours:02}:{mins:02}:{secs:02}"


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
        return False, f"🔒 <b>{sc('Bot is in private mode.')}</b>\n{sc('Only admins can use it right now.')}"

    if mode == "maintenance":
        msg = await CosmicBotz.get_maintenance_message()
        return False, msg or f"🔧 <b>{sc('Bot is under maintenance.')}</b>\n{sc('Please check back soon.')}"

    if mode == "beta":
        user = await CosmicBotz.get_user(user_id)
        if user and user.get("is_premium"):
            return True, ""
        return False, f"🔵 <b>{sc('Bot is in Beta mode.')}</b>\n{sc('Only ⭐ Premium users have access right now.')}"

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
        f"👑 <b>{sc('Admin Panel')}</b>\n\n"
        f"👥 {sc('Users:')}  <b>{tu}</b>\n"
        f"📤 {sc('Posts:')}  <b>{tp}</b>\n"
        f"🌐 {sc('Mode:')}   <code>{mode}</code>",
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
            f"🌐 <b>{sc('Bot Mode')}</b>\n\n{sc('Current:')} <code>{current}</code>\n\n"
            f"{sc('Usage:')} <code>/mode [{'|'.join(valid)}]</code>",
            reply_markup=mode_kb(current),
        )
        return
    new_mode = args[0]
    await CosmicBotz.set_bot_mode(new_mode)
    await message.answer(f"✅ {sc('Mode set to')} <code>{new_mode}</code>.")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return
    await fsm.set(message.from_user.id, {"step": "adm_broadcast"})
    await message.answer(f"📢 {sc('Send the message to broadcast to all users:')}")


@router.message(Command("log"))
async def cmd_log(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        f"📋 <b>{sc('Logs')}</b>\n\n{sc('How do you want to receive the logs?')}",
        reply_markup=log_kb(),
    )


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args or not args[0].isdigit():
        await message.answer(f"{sc('Usage:')} /ban <code>user_id</code>")
        return
    uid = int(args[0])
    await CosmicBotz.ban_user(uid)
    await message.answer(f"⛔ {sc('User')} <code>{uid}</code> {sc('banned.')}")
    try:
        await message.bot.send_message(uid, f"⛔ {sc('You have been')} <b>{sc('banned')}</b> {sc('from this bot.')}")
    except Exception:
        pass


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args or not args[0].isdigit():
        await message.answer(f"{sc('Usage:')} /unban <code>user_id</code>")
        return
    uid = int(args[0])
    await CosmicBotz.unban_user(uid)
    await message.answer(f"✅ {sc('User')} <code>{uid}</code> {sc('unbanned.')}")
    try:
        await message.bot.send_message(uid, f"✅ {sc('You have been')} <b>{sc('unbanned')}</b>. {sc('Welcome back!')}")
    except Exception:
        pass


@router.message(Command("addpremium"))
async def cmd_addpremium(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args or not args[0].isdigit():
        await message.answer(f"{sc('Usage:')} /addpremium <code>user_id</code>")
        return
    uid = int(args[0])
    await CosmicBotz.set_premium(uid, True)
    await message.answer(f"⭐ <code>{uid}</code> {sc('upgraded to Premium.')}")
    try:
        await message.bot.send_message(
    uid,
    f"🎉 <b>{sc('You\\'ve been upgraded to ⭐ Premium!')}</b>\n{sc('Enjoy unlimited access.')}",
)
    except Exception:
        pass


@router.message(Command("revokepremium"))
async def cmd_revokepremium(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args or not args[0].isdigit():
        await message.answer(f"{sc('Usage:')} /revokepremium <code>user_id</code>")
        return
    uid = int(args[0])
    await CosmicBotz.set_premium(uid, False)
    await message.answer(f"✅ {sc('Premium revoked for')} <code>{uid}</code>.")
    try:
        await message.bot.send_message(uid, f"ℹ️ {sc('Your')} <b>{sc('Premium')}</b> {sc('access has been revoked.')}")
    except Exception:
        pass


@router.message(Command("userinfo"))
async def cmd_userinfo(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args or not args[0].lstrip("-").isdigit():
        await message.answer(f"{sc('Usage:')} /userinfo <code>user_id</code>")
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
            f"{sc('Usage:')} <code>/maintenance Your maintenance message here</code>\n\n"
            f"{sc('This sets the bot to maintenance mode and saves the message shown to users.')}"
        )
        return
    text = parts[1].strip()
    await CosmicBotz.set_bot_mode("maintenance")
    await CosmicBotz.set_maintenance_message(text)
    await message.answer(
        f"🔧 <b>{sc('Maintenance mode ON')}</b>\n\n"
        f"{sc('Message shown to users:')}\n<i>{text}</i>\n\n"
        f"{sc('Use')} <code>/mode public</code> {sc('to bring the bot back online.')}"
    )


@router.message(Command("update"))
async def cmd_update(message: Message):
    """Trigger a redeploy from latest Git commit on Render."""
    if not is_admin(message.from_user.id):
        return
    await _trigger_render_deploy(message)


# ── Render deploy helpers ─────────────────────────────────────────────────────

import re as _re


def _parse_service_id(hook_url: str) -> str:
    """Extract  srv-xxxx  from the deploy hook URL — no config needed."""
    m = _re.search(r"(srv-[a-z0-9]+)", hook_url)
    return m.group(1) if m else ""


async def _render_api_get(path: str, api_key: str):
    """Generic authenticated GET against the Render v1 API."""
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"https://api.render.com/v1{path}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                return await r.json() if r.status == 200 else None
    except Exception:
        return None


async def _fetch_render_info(service_id: str, api_key: str) -> tuple[str, str, str]:
    """
    Returns (deployed_sha, github_repo, branch) using only the Render API.
    github_repo is  owner/repo  — parsed from the repo URL Render stores.
    """
    deployed_sha = branch = gh_repo = ""

    # 1. Latest deploy → gives currently deployed commit SHA
    deploys = await _render_api_get(f"/services/{service_id}/deploys?limit=1", api_key)
    if deploys and isinstance(deploys, list):
        deployed_sha = deploys[0].get("deploy", {}).get("commit", {}).get("id", "")

    # 2. Service details → gives connected repo URL + branch
    svc = await _render_api_get(f"/services/{service_id}", api_key)
    if svc:
        details = svc.get("service", {}).get("serviceDetails", {})
        branch  = details.get("branch", "main")
        raw_url = details.get("repo", "")
        # https://github.com/owner/repo  or  git@github.com:owner/repo.git
        m = _re.search(r"github\.com[/:](.+?)(?:\.git)?$", raw_url)
        if m:
            gh_repo = m.group(1)

    return deployed_sha, gh_repo, branch


async def _latest_github_sha(repo: str, branch: str) -> str:
    """Latest commit SHA from GitHub — no token needed for public repos."""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"https://api.github.com/repos/{repo}/commits/{branch}",
                headers={"Accept": "application/vnd.github+json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                data = await r.json() if r.status == 200 else {}
                return data.get("sha", "")
    except Exception:
        return ""


async def _trigger_render_deploy(target: Message):
    """
    Auto-detects service ID, repo and branch entirely from Render API.
    Only needs RENDER_DEPLOY_HOOK + RENDER_API_KEY — nothing else.
    """
    hook    = getattr(cfg, "RENDER_DEPLOY_HOOK", "")
    api_key = getattr(cfg, "RENDER_API_KEY",     "")

    if not hook:
        await target.answer(
            "❌ <b>RENDER_DEPLOY_HOOK</b> is not set.\n\n"
            "Add it to your <code>.env</code> and <code>config.py</code>."
        )
        return

    msg = await target.answer("🔍 <b>Checking for new commits...</b>")

    # ── Commit comparison ─────────────────────────────────────────────────────
    if api_key:
        service_id = _parse_service_id(hook)
        deployed_sha, gh_repo, branch = await _fetch_render_info(service_id, api_key)
        latest_sha = await _latest_github_sha(gh_repo, branch) if gh_repo else ""

        if deployed_sha and latest_sha:
            if deployed_sha == latest_sha:
                await msg.edit_text(
                    f"✅ <b>Already up to date!</b>\n\n"
                    f"🔖 Deployed: <code>{deployed_sha[:7]}</code>\n"
                    f"🌿 Branch:   <code>{branch}</code>\n\n"
                    "<i>No redeploy needed.</i>"
                )
                return

            await msg.edit_text(
                f"🆕 <b>New commit found!</b>\n\n"
                f"🔖 Deployed: <code>{deployed_sha[:7]}</code>\n"
                f"🚀 Latest:   <code>{latest_sha[:7]}</code>\n\n"
                "⏳ Triggering deploy..."
            )
        else:
            await msg.edit_text("⚠️ <b>Could not compare commits.</b> Triggering deploy anyway...")
    else:
        await msg.edit_text("🔄 <b>Triggering deploy on Render...</b>")

    # ── Fire the deploy hook ──────────────────────────────────────────────────
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
    tu     = await CosmicBotz.total_users()
    tp     = await CosmicBotz.total_posts()
    mode   = await CosmicBotz.get_bot_mode()
    pu     = await CosmicBotz.total_premium_users()
    bu     = await CosmicBotz.total_banned_users()
    active = await CosmicBotz.active_users_today()
    text = (
        f"📊 <b>{sc('Global Stats')}</b>\n\n"
        f"👥 {sc('Total Users:')}   <b>{tu}</b>\n"
        f"🟢 {sc('Active Today:')}  <b>{active}</b>\n"
        f"⭐ {sc('Premium:')}       <b>{pu}</b>\n"
        f"⛔ {sc('Banned:')}        <b>{bu}</b>\n"
        f"📤 {sc('Total Posts:')}   <b>{tp}</b>\n"
        f"🌐 {sc('Bot Mode:')}      <code>{mode}</code>\n"
        f"⏱ {sc('Uptime:')}        <code>{_fmt_uptime()}</code>"
    )
    if isinstance(target, Message):
        await target.answer(text, reply_markup=admin_kb())
    else:
        await target.edit_text(text, reply_markup=admin_kb())


async def _send_userinfo(target: Message, uid: int):
    user = await CosmicBotz.get_user(uid)
    if not user:
        await target.answer(f"❌ {sc('User not found in DB.')}")
        return
    s        = user.get("settings", {})
    joined   = user.get("joined", "?")
    last     = user.get("last_seen", "?")
    if isinstance(joined, datetime):
        joined = joined.strftime("%Y-%m-%d")
    if isinstance(last, datetime):
        last = last.strftime("%Y-%m-%d %H:%M")
    await target.answer(
        f"👤 <b>{sc('User Info')}</b>\n\n"
        f"{sc('ID:')}         <code>{uid}</code>\n"
        f"{sc('Name:')}       {user.get('full_name', 'N/A')}\n"
        f"{sc('Username:')}   @{user.get('username', 'N/A')}\n"
        f"{sc('Joined:')}     <code>{joined}</code>\n"
        f"{sc('Last Seen:')}  <code>{last}</code>\n"
        f"{sc('Posts:')}      <b>{user.get('post_count', 0)}</b>\n"
        f"{sc('Premium:')}    {'⭐ ' + sc('Yes') if user.get('is_premium') else sc('No')}\n"
        f"{sc('Banned:')}     {'⛔ ' + sc('Yes') if user.get('is_banned') else sc('No')}\n"
        f"{sc('Channel:')}    <code>{s.get('channel_id') or sc('Not set')}</code>\n"
        f"{sc('Watermark:')}  <code>{s.get('watermark') or sc('Not set')}</code>\n"
        f"{sc('Template:')}   <code>{s.get('active_template', 'default')}</code>"
    )


# ── Broadcast ─────────────────────────────────────────────────────────────────

async def do_broadcast(message: Message, text: str):
    """Called from content.py handle_text_input when step=adm_broadcast."""
    await fsm.clear(message.from_user.id)
    user_ids = await CosmicBotz.get_all_user_ids()
    status = await message.answer(f"📤 {sc('Broadcasting to')} <b>{len(user_ids)}</b> {sc('users...')}")
    ok = fail = 0
    for uid in user_ids:
        try:
            await message.bot.send_message(uid, f"📢 <b>{sc('Announcement')}</b>\n\n{text}")
            ok += 1
        except Exception:
            fail += 1
        if ok % 25 == 0:
            await asyncio.sleep(1)
    await status.edit_text(
        f"✅ {sc('Broadcast done!')}\n"
        f"✔ {sc('Sent:')} <b>{ok}</b>   ✘ {sc('Failed:')} <b>{fail}</b>"
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_"))
async def adm_callback(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer(sc("⛔ Admin only."), show_alert=True)
        return
    await cb.answer()
    uid  = cb.from_user.id
    data = cb.data

    if data == "adm_back":
        tu   = await CosmicBotz.total_users()
        tp   = await CosmicBotz.total_posts()
        mode = await CosmicBotz.get_bot_mode()
        await cb.message.edit_text(
            f"👑 <b>{sc('Admin Panel')}</b>\n\n"
            f"👥 {sc('Users:')} <b>{tu}</b>\n"
            f"📤 {sc('Posts:')} <b>{tp}</b>\n"
            f"🌐 {sc('Mode:')}  <code>{mode}</code>",
            reply_markup=admin_kb(),
        )

    elif data == "adm_close":
        try:
            await cb.message.delete()
        except Exception:
            pass

    elif data == "adm_stats":
        tu     = await CosmicBotz.total_users()
        tp     = await CosmicBotz.total_posts()
        mode   = await CosmicBotz.get_bot_mode()
        pu     = await CosmicBotz.total_premium_users()
        bu     = await CosmicBotz.total_banned_users()
        active = await CosmicBotz.active_users_today()
        await cb.message.edit_text(
            f"📊 <b>{sc('Global Stats')}</b>\n\n"
            f"👥 {sc('Total Users:')}   <b>{tu}</b>\n"
            f"🟢 {sc('Active Today:')}  <b>{active}</b>\n"
            f"⭐ {sc('Premium:')}       <b>{pu}</b>\n"
            f"⛔ {sc('Banned:')}        <b>{bu}</b>\n"
            f"📤 {sc('Total Posts:')}   <b>{tp}</b>\n"
            f"🌐 {sc('Bot Mode:')}      <code>{mode}</code>\n"
            f"⏱ {sc('Uptime:')}        <code>{_fmt_uptime()}</code>",
            reply_markup=admin_kb(),
        )

    elif data == "adm_broadcast":
        await fsm.set(uid, {"step": "adm_broadcast"})
        await cb.message.edit_text(f"📢 {sc('Send the broadcast message now:')}")

    elif data == "adm_mode":
        current = await CosmicBotz.get_bot_mode()
        await cb.message.edit_text(
            f"🌐 <b>{sc('Bot Mode')}</b>\n\n{sc('Current:')} <code>{current}</code>\n\n"
            f"🟢 <b>{sc('Public')}</b> — {sc('everyone can use the bot')}\n"
            f"🔴 <b>{sc('Private')}</b> — {sc('admin only')}\n"
            f"🟡 <b>{sc('Maintenance')}</b> — {sc('shows maintenance message')}\n"
            f"🔵 <b>{sc('Beta')}</b> — {sc('premium users only')}\n"
            f"🟠 <b>{sc('Readonly')}</b> — {sc('browsing allowed, no posting')}",
            reply_markup=mode_kb(current),
        )

    elif data.startswith("adm_setmode_"):
        new_mode = data.replace("adm_setmode_", "")
        await CosmicBotz.set_bot_mode(new_mode)
        await cb.answer(f"✅ {sc('Mode')} → {new_mode}", show_alert=True)
        await cb.message.edit_text(
            f"🌐 <b>{sc('Bot Mode')}</b>\n\n{sc('Current:')} <code>{new_mode}</code>\n\n"
            f"🟢 <b>{sc('Public')}</b> — {sc('everyone can use the bot')}\n"
            f"🔴 <b>{sc('Private')}</b> — {sc('admin only')}\n"
            f"🟡 <b>{sc('Maintenance')}</b> — {sc('shows maintenance message')}\n"
            f"🔵 <b>{sc('Beta')}</b> — {sc('premium users only')}\n"
            f"🟠 <b>{sc('Readonly')}</b> — {sc('browsing allowed, no posting')}",
            reply_markup=mode_kb(new_mode),
        )

    elif data == "adm_log":
        await cb.message.edit_text(
            f"📋 <b>{sc('Logs')}</b>\n\n{sc('How do you want to receive the logs?')}",
            reply_markup=log_kb(),
        )

    elif data == "adm_log_text":
        raw  = _log_buffer.get_text()
        safe = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        tail = safe[-3800:] if len(safe) > 3800 else safe
        await cb.message.edit_text(
            f"📋 <b>{sc('Recent Logs')}</b>\n\n<pre>{tail}</pre>",
            reply_markup=log_kb(),
        )

    elif data == "adm_log_file":
        raw  = _log_buffer.get_text()
        name = f"logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
        buf  = io.BytesIO(raw.encode("utf-8"))
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.bot.send_document(
            chat_id=cb.message.chat.id,
            document=BufferedInputFile(buf.getvalue(), filename=name),
            caption=f"📄 <b>{sc('Full log file')}</b>",
            reply_markup=log_kb(),
        )

    elif data == "adm_log_clear":
        _log_buffer.clear()
        await cb.answer(sc("🗑 Logs cleared."), show_alert=True)
        await cb.message.edit_text(
            f"📋 <b>{sc('Logs')}</b>\n\n{sc('How do you want to receive the logs?')}",
            reply_markup=log_kb(),
        )

    elif data == "adm_users":
        await cb.message.edit_text(
            f"👥 <b>{sc('User Management')}</b>\n\n{sc('Choose an action:')}",
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
            "adm_userinfo_prompt": f"🔍 {sc('Send the')} <b>{sc('user ID')}</b> {sc('to look up:')}",
            "adm_ban_prompt":      f"⛔ {sc('Send the')} <b>{sc('user ID')}</b> {sc('to ban:')}",
            "adm_unban_prompt":    f"✅ {sc('Send the')} <b>{sc('user ID')}</b> {sc('to unban:')}",
            "adm_premium_prompt":  f"⭐ {sc('Send the')} <b>{sc('user ID')}</b> {sc('to grant Premium:')}",
            "adm_revoke_prompt":   f"❌ {sc('Send the')} <b>{sc('user ID')}</b> {sc('to revoke Premium:')}",
        }
        await fsm.set(uid, {"step": step_map[data]})
        await cb.message.edit_text(prompt_map[data])

    elif data == "adm_maintenance":
        current_msg = await CosmicBotz.get_maintenance_message()
        await cb.message.edit_text(
            f"🔧 <b>{sc('Maintenance Settings')}</b>\n\n"
            f"{sc('Current message:')}\n<i>{current_msg or sc('Not set')}</i>",
            reply_markup=maintenance_kb(),
        )

    elif data == "adm_set_maint_msg":
        await fsm.set(uid, {"step": "adm_maint_msg"})
        await cb.message.edit_text(
            f"🔧 {sc('Send the')} <b>{sc('maintenance message')}</b> {sc('users will see:')}\n\n"
            f"<i>{sc('Example: We are upgrading the bot, back in 30 mins!')} 🚀</i>"
        )

    elif data == "adm_update":
        await _trigger_render_deploy(cb.message)