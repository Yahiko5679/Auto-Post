"""
Settings — /settings  /setwatermark  /setchannel
Handles all cfg_ callbacks and text input for multi-step flows.
"""
from pyrofork import Client, filters
from pyrofork.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import CosmicBotz
from utils.fsm import fsm
from utils.helpers import settings_kb, quality_kb, audio_kb, banned_check, track_user
import config as cfg

# All commands that should NOT be caught by the text input handler
_ALL_CMDS = [
    "start", "help", "movie", "tvshow", "anime", "manhwa",
    "settings", "setwatermark", "setchannel", "stats",
    "setformat", "myformat", "templates",
    "admin", "broadcast", "ban", "unban",
    "addpremium", "revokepremium", "userinfo", "globalstats",
]


@Client.on_message(filters.command("settings") & filters.private)
@banned_check
@track_user
async def cmd_settings(client: Client, message: Message):
    await _send_settings(message.from_user.id, message)


@Client.on_message(filters.command("setwatermark") & filters.private)
@banned_check
async def cmd_setwatermark(client: Client, message: Message):
    await fsm.set(message.from_user.id, {"step": "cfg_watermark"})
    await message.reply(
        "🖋 **Set Watermark**\n\n"
        "Send your watermark text (e.g. `@YourChannel`)\n"
        "Send `clear` to remove it."
    )


@Client.on_message(filters.command("setchannel") & filters.private)
@banned_check
async def cmd_setchannel(client: Client, message: Message):
    await fsm.set(message.from_user.id, {"step": "cfg_channel"})
    await message.reply(
        "📺 **Set Channel**\n\n"
        "Send your channel username or ID.\n"
        "Example: `@MyAnimeChannel`\n\n"
        "⚠️ Make sure this bot is **admin** in your channel first!"
    )


async def _send_settings(user_id: int, target):
    s    = await CosmicBotz.get_user_settings(user_id)
    user = await CosmicBotz.get_user(user_id)
    plan = "⭐ Premium" if user and user.get("is_premium") else "Free"
    text = (
        f"⚙️ **Settings**  `[{plan}]`\n\n"
        f"🖋 Watermark:  `{s.get('watermark') or 'Not set'}`\n"
        f"📺 Channel:    `{s.get('channel_id') or 'Not set'}`\n"
        f"🎞 Quality:    `{s.get('quality', cfg.DEFAULT_QUALITY)}`\n"
        f"🔊 Audio:      `{s.get('audio', cfg.DEFAULT_AUDIO)}`\n"
        f"📋 Template:   `{s.get('active_template', 'default')}`"
    )
    if hasattr(target, "reply"):
        await target.reply(text, reply_markup=settings_kb())
    else:
        await target.edit(text, reply_markup=settings_kb())


# ── Settings callbacks ────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^cfg_"))
async def cfg_callback(client: Client, cb: CallbackQuery):
    await cb.answer()
    uid  = cb.from_user.id
    data = cb.data

    if data == "cfg_open":
        await _send_settings(uid, cb.message)

    elif data == "cfg_watermark":
        await fsm.set(uid, {"step": "cfg_watermark"})
        await cb.message.edit(
            "🖋 **Set Watermark**\n\n"
            "Send your watermark text (e.g. `@YourChannel`)\n"
            "Send `clear` to remove."
        )

    elif data == "cfg_channel":
        await fsm.set(uid, {"step": "cfg_channel"})
        await cb.message.edit(
            "📺 **Set Channel**\n\n"
            "Send your channel username or ID.\n"
            "⚠️ Bot must be **admin** in the channel!"
        )

    elif data == "cfg_quality":
        await cb.message.edit("🎞 **Select Default Quality:**", reply_markup=quality_kb())

    elif data == "cfg_audio":
        await cb.message.edit("🔊 **Select Default Audio:**", reply_markup=audio_kb())

    elif data.startswith("cfg_setquality|"):
        val = data.split("|", 1)[1]
        await CosmicBotz.update_user_settings(uid, {"quality": val})
        await cb.answer(f"✅ Quality set!", show_alert=True)
        await _send_settings(uid, cb.message)

    elif data.startswith("cfg_setaudio|"):
        val = data.split("|", 1)[1]
        await CosmicBotz.update_user_settings(uid, {"audio": val})
        await cb.answer(f"✅ Audio set!", show_alert=True)
        await _send_settings(uid, cb.message)

    elif data == "cfg_templates":
        from plugins.templates import show_templates
        await show_templates(uid, cb.message)

    elif data == "cfg_stats":
        user  = await CosmicBotz.get_user(uid)
        posts = user.get("post_count", 0) if user else 0
        plan  = "⭐ Premium" if user and user.get("is_premium") else "Free"
        await cb.message.edit(
            f"📊 **My Stats**\n\nTotal Posts: **{posts}**\nPlan: **{plan}**",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="cfg_back")
            ]])
        )

    elif data == "cfg_back":
        await _send_settings(uid, cb.message)

    elif data == "cfg_close":
        await cb.message.delete()


# ── Text input router ─────────────────────────────────────────────────────────

@Client.on_message(filters.text & filters.private & ~filters.command(_ALL_CMDS))
async def handle_text(client: Client, message: Message):
    uid   = message.from_user.id
    state = await fsm.get(uid)
    if not state:
        return
    step = state.get("step", "")
    text = message.text.strip()

    if step == "cfg_watermark":
        if text.lower() == "clear":
            await CosmicBotz.update_user_settings(uid, {"watermark": ""})
            await message.reply("✅ Watermark cleared.")
        else:
            await CosmicBotz.update_user_settings(uid, {"watermark": text})
            await message.reply(f"✅ Watermark set to `{text}`")
        await fsm.clear(uid)

    elif step == "cfg_channel":
        if not (text.startswith("@") or text.lstrip("-").isdigit()):
            await message.reply("❌ Use `@channel` format or a numeric chat ID.")
            return
        await CosmicBotz.update_user_settings(uid, {"channel_id": text})
        await message.reply(f"✅ Channel linked: `{text}`\nMake sure the bot is admin there!")
        await fsm.clear(uid)

    elif step == "tpl_name":
        if " " in text or len(text) > 32:
            await message.reply("❌ Name must be ≤ 32 chars with no spaces. Try again:")
            return
        await fsm.update(uid, {"step": "tpl_body", "tpl_name": text})
        await message.reply(
            f"✅ Name: **{text}**\n\n"
            "Now send the **template body**.\n"
            "Use tokens like `{title}`, `{imdb_rating}`, `{genres}` etc.\n"
            "Must include `{title}`."
        )

    elif step == "tpl_body":
        if "{title}" not in text:
            await message.reply("⚠️ Template must contain `{title}`. Try again:")
            return
        name = state.get("tpl_name", "unnamed")
        await CosmicBotz.save_template(uid, name, text)
        await CosmicBotz.update_user_settings(uid, {"active_template": name})
        await fsm.clear(uid)
        await message.reply(
            f"✅ **Template '{name}' saved and activated!**\n"
            "Use /templates to manage all your templates."
        )

    elif step == "adm_broadcast":
        from plugins.admin import do_broadcast
        await do_broadcast(client, message, text)
