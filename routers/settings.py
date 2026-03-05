from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import CosmicBotz
from formatter.engine import sc
from utils.fsm import fsm
import config as cfg

router = Router()


# ── Keyboards ─────────────────────────────────────────────────────────────────

def settings_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🖋 Watermark",       callback_data="cfg_watermark")
    kb.button(text="🖼 Logo Watermark",  callback_data="cfg_wm_logo")
    kb.button(text="📺 Channel",          callback_data="cfg_channel")
    kb.button(text="🎞 Quality",          callback_data="cfg_quality")
    kb.button(text="🔊 Audio",            callback_data="cfg_audio")
    kb.button(text="📋 Templates",        callback_data="cfg_templates")
    kb.button(text="🔗 Button Sets",      callback_data="cfg_btnsets")
    kb.button(text="🔘 Default Buttons",  callback_data="cfg_defbuttons")
    kb.button(text="📊 My Stats",         callback_data="cfg_stats")
    kb.button(text="❌ Close",             callback_data="cfg_close")
    kb.adjust(2, 2, 2, 2, 1, 1)
    return kb.as_markup()


def quality_kb():
    kb = InlineKeyboardBuilder()
    for q in ["480p", "720p", "1080p", "4K", "480p | 720p | 1080p"]:
        kb.button(text=q, callback_data=f"cfg_setquality|{q}")
    kb.button(text="🔙 Back", callback_data="cfg_open")
    kb.adjust(3, 1, 1)
    return kb.as_markup()


def audio_kb():
    kb = InlineKeyboardBuilder()
    for a in ["Hindi", "English", "Hindi | English", "Multi Audio"]:
        kb.button(text=a, callback_data=f"cfg_setaudio|{a}")
    kb.button(text="🔙 Back", callback_data="cfg_open")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


# ── Settings display ──────────────────────────────────────────────────────────

async def _show_settings(uid: int, target):
    await CosmicBotz.upsert_user(uid, "", "")
    s    = await CosmicBotz.get_user_settings(uid)
    user = await CosmicBotz.get_user(uid)
    plan = "⭐ Premium" if user and user.get("is_premium") else "Free"

    logo_status = "✅ Set" if s.get("watermark_logo") else "Not set"
    dfl_btns    = s.get("default_buttons", [])
    dfl_preview = ", ".join(b["text"] for b in dfl_btns[:3]) if dfl_btns else "None"
    if len(dfl_btns) > 3:
        dfl_preview += f" +{len(dfl_btns) - 3} more"

    text = (
        f"⚙️ <b>{sc('Settings')}</b>  <code>[{plan}]</code>\n\n"
        f"🖋 {sc('Watermark:')}       <code>{s.get('watermark') or sc('Not set')}</code>\n"
        f"🖼 {sc('Logo:')}            <code>{logo_status}</code>\n"
        f"📺 {sc('Channel:')}         <code>{s.get('channel_id') or sc('Not set')}</code>\n"
        f"🎞 {sc('Quality:')}         <code>{s.get('quality', cfg.DEFAULT_QUALITY)}</code>\n"
        f"🔊 {sc('Audio:')}           <code>{s.get('audio', cfg.DEFAULT_AUDIO)}</code>\n"
        f"📋 {sc('Template:')}        <code>{s.get('active_template', 'default')}</code>\n"
        f"🔗 {sc('Button Set:')}      <code>{s.get('active_btn_set') or 'none'}</code>\n"
        f"🔘 {sc('Default Buttons:')} <code>{dfl_preview}</code>"
    )
    if isinstance(target, Message):
        await target.answer(text, reply_markup=settings_kb())
    else:
        try:
            await target.edit_text(text, reply_markup=settings_kb())
        except Exception:
            pass


# ── Commands ──────────────────────────────────────────────────────────────────

@router.message(Command("settings"))
async def cmd_settings(message: Message):
    await _show_settings(message.from_user.id, message)


@router.message(Command("setwatermark"))
async def cmd_setwatermark(message: Message):
    await fsm.set(message.from_user.id, {"step": "cfg_watermark"})
    await message.answer(
        f"🖋 <b>{sc('Set Text Watermark')}</b>\n\n"
        f"{sc('Send your watermark text.')}\n"
        f"{sc('Example:')} <code>@YourChannel</code>  {sc('or')}  <code>Anime Metrix</code>\n\n"
        f"{sc('This appears as')} <b>{sc('plain text')}</b> {sc('on the thumbnail.')}\n"
        f"{sc('Send')} <code>clear</code> {sc('to remove.')}"
    )


@router.message(Command("setchannel"))
async def cmd_setchannel(message: Message):
    await fsm.set(message.from_user.id, {"step": "cfg_channel"})
    await message.answer(
        f"📺 <b>{sc('Set Channel')}</b>\n\n"
        f"{sc('Send your channel username or numeric ID.')}\n"
        f"{sc('Example:')} <code>@MyAnimeChannel</code>\n\n"
        f"⚠️ {sc('Make sure the bot is')} <b>{sc('admin')}</b> {sc('in your channel first!')}"
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cfg_"))
async def cfg_callback(cb: CallbackQuery):
    await cb.answer()
    uid  = cb.from_user.id
    data = cb.data

    if data in ("cfg_open", "cfg_back"):
        await _show_settings(uid, cb.message)

    elif data == "cfg_watermark":
        await fsm.set(uid, {"step": "cfg_watermark"})
        s       = await CosmicBotz.get_user_settings(uid)
        current = s.get("watermark") or sc("Not set")
        try:
            await cb.message.edit_text(
                f"🖋 <b>{sc('Set Text Watermark')}</b>\n\n"
                f"{sc('Current:')} <code>{current}</code>\n\n"
                f"{sc('Send new watermark text — displayed cleanly on thumbnail.')}\n"
                f"{sc('Example:')} <code>@YourChannel</code>  {sc('or')}  <code>Anime Metrix</code>\n\n"
                f"{sc('Send')} <code>clear</code> {sc('to remove.')}"
            )
        except Exception:
            pass

    elif data == "cfg_wm_logo":
        await fsm.set(uid, {"step": "cfg_wm_logo"})
        s        = await CosmicBotz.get_user_settings(uid)
        has_logo = sc("✅ Logo is set.") if s.get("watermark_logo") else sc("No logo set yet.")
        kb       = InlineKeyboardBuilder()
        if s.get("watermark_logo"):
            kb.button(text="🗑 Remove Logo", callback_data="cfg_wm_logo_clear")
        kb.button(text="🔙 Back", callback_data="cfg_open")
        kb.adjust(1)
        try:
            await cb.message.edit_text(
                f"🖼 <b>{sc('Logo Watermark')}</b>\n\n"
                f"{has_logo}\n\n"
                f"{sc('Send a')} <b>{sc('photo')}</b> {sc('to use as your logo watermark.')}\n"
                f"{sc('It will appear in the top-right corner of every thumbnail.')}\n\n"
                f"<i>{sc('Tip: Use a PNG with transparent background for best results.')}\n"
                f"{sc('Logo is displayed alongside or instead of text watermark.')}</i>",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            pass

    elif data == "cfg_wm_logo_clear":
        await CosmicBotz.update_user_settings(uid, {"watermark_logo": ""})
        await cb.answer(sc("✅ Logo removed."), show_alert=True)
        await _show_settings(uid, cb.message)

    elif data == "cfg_channel":
        await fsm.set(uid, {"step": "cfg_channel"})
        try:
            await cb.message.edit_text(
                f"📺 <b>{sc('Set Channel')}</b>\n\n"
                f"{sc('Send')} <code>@channel</code> {sc('or numeric ID.')}\n"
                f"⚠️ {sc('Bot must be admin in the channel!')}"
            )
        except Exception:
            pass

    elif data == "cfg_quality":
        try:
            await cb.message.edit_text(
                f"🎞 <b>{sc('Select Default Quality:')}</b>",
                reply_markup=quality_kb(),
            )
        except Exception:
            pass

    elif data == "cfg_audio":
        try:
            await cb.message.edit_text(
                f"🔊 <b>{sc('Select Default Audio:')}</b>",
                reply_markup=audio_kb(),
            )
        except Exception:
            pass

    elif data.startswith("cfg_setquality|"):
        val = data.split("|", 1)[1]
        await CosmicBotz.update_user_settings(uid, {"quality": val})
        await cb.answer(sc("✅ Quality updated!"), show_alert=True)
        await _show_settings(uid, cb.message)

    elif data.startswith("cfg_setaudio|"):
        val = data.split("|", 1)[1]
        await CosmicBotz.update_user_settings(uid, {"audio": val})
        await cb.answer(sc("✅ Audio updated!"), show_alert=True)
        await _show_settings(uid, cb.message)

    elif data == "cfg_templates":
        from routers.templates import show_templates
        await show_templates(uid, cb.message)

    elif data == "cfg_btnsets":
        from routers.buttons import show_button_sets
        await show_button_sets(uid, cb.message)

    elif data == "cfg_defbuttons":
        await fsm.set(uid, {"step": "cfg_defbtn_name"})
        s        = await CosmicBotz.get_user_settings(uid)
        existing = s.get("default_buttons", [])
        preview  = (
            "\n".join(f"  • {b['text']} → {b.get('url', '')[:30]}" for b in existing)
            or f"  {sc('None')}"
        )
        try:
            await cb.message.edit_text(
                f"🔘 <b>{sc('Default Buttons')}</b>\n\n"
                f"{sc('These buttons auto-appear on every post.')}\n\n"
                f"<b>{sc('Current:')}</b>\n{preview}\n\n"
                f"{sc('Send a button in format:')}\n"
                f"<code>Button Name | https://link.com | row</code>\n\n"
                f"<b>{sc('Row')}</b> = 1, 2, 3 ({sc('which row to place it')})\n\n"
                f"{sc('Examples:')}\n"
                f"<code>▶️ Watch Now | https://t.me/yourchannel | 1</code>\n"
                f"<code>📥 Download | https://yoursite.com | 1</code>\n\n"
                f"{sc('Send')} <code>clear</code> {sc('to remove all default buttons.')}"
            )
        except Exception:
            pass

    elif data == "cfg_stats":
        user  = await CosmicBotz.get_user(uid)
        posts = user.get("post_count", 0) if user else 0
        plan  = "⭐ Premium" if user and user.get("is_premium") else "Free"
        kb    = InlineKeyboardBuilder()
        kb.button(text="🔙 Back", callback_data="cfg_back")
        try:
            await cb.message.edit_text(
                f"📊 <b>{sc('My Stats')}</b>\n\n"
                f"{sc('Total Posts:')} <b>{posts}</b>\n"
                f"{sc('Plan:')} <b>{plan}</b>",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            pass

    elif data == "cfg_close":
        try:
            await cb.message.delete()
        except Exception:
            pass
