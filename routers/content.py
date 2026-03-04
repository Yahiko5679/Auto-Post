import io
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import CosmicBotz
from fetchers.tmdb import TMDbFetcher
from fetchers.jikan import JikanFetcher
from fetchers.anilist import AniListFetcher
from formatter.engine import FormatEngine
from thumbnail.processor import build_thumbnail, process_custom_thumbnail
from utils.fsm import fsm
from utils.helpers import (
    extract_query, search_kb, thumbnail_kb, preview_kb,
    template_kb, add_button_start_kb, button_manage_kb, default_buttons_kb,
)

from routers.admin import is_admin, check_mode 

logger = logging.getLogger(__name__)
router = Router()

_tmdb    = TMDbFetcher()
_jikan   = JikanFetcher()
_anilist = AniListFetcher()
_fmt     = FormatEngine()

FETCHERS = {
    "movie":  (_tmdb.search_movies,    _tmdb.get_movie,      "movie"),
    "tvshow": (_tmdb.search_tv,        _tmdb.get_tv,         "tv"),
    "anime":  (_jikan.search_anime,    _jikan.get_anime,     "anime"),
    "manhwa": (_anilist.search_manhwa, _anilist.get_manhwa,  "manhwa"),
}
EXAMPLES = {
    "movie":  "Inception",
    "tvshow": "Breaking Bad",
    "anime":  "Attack on Titan",
    "manhwa": "Solo Leveling",
}
PREFIX_TO_CAT = {"movie": "movie", "tv": "tvshow", "anime": "anime", "manhwa": "manhwa"}
CAT_TO_PREFIX = {"movie": "movie", "tvshow": "tv", "anime": "anime", "manhwa": "manhwa"}

MAX_COLS    = 4
MAX_ROWS    = 4
MAX_BUTTONS = MAX_COLS * MAX_ROWS


# ── Button keyboard builders ──────────────────────────────────────────────────

def build_post_keyboard(buttons: list) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    kb   = InlineKeyboardBuilder()
    rows: dict[int, int] = {}
    for btn in buttons:
        if btn.get("url"):
            kb.button(text=btn["text"], url=btn["url"])
        elif btn.get("callback_data"):
            kb.button(text=btn["text"], callback_data=btn["callback_data"])
        r = btn.get("row", 0)
        rows[r] = rows.get(r, 0) + 1
    if rows:
        kb.adjust(*[rows[r] for r in sorted(rows.keys())])
    else:
        kb.adjust(2)
    return kb.as_markup()


def _layout_preview(buttons: list) -> str:
    if not buttons:
        return "<i>No buttons yet.</i>"
    rows: dict[int, list] = {}
    for btn in buttons:
        rows.setdefault(btn.get("row", 0), []).append(btn["text"])
    return "\n".join(
        "  [" + "]  [".join(rows[r]) + "]"
        for r in sorted(rows.keys())
    )


def _position_kb(prefix: str, current_buttons: list) -> InlineKeyboardMarkup:
    rows: dict[int, int] = {}
    for btn in current_buttons:
        r = btn.get("row", 0)
        rows[r] = rows.get(r, 0) + 1
    kb = InlineKeyboardBuilder()
    for r in sorted(rows.keys()):
        if rows[r] < MAX_COLS:
            kb.button(
                text=f"➕ Row {r + 1}  [{rows[r]}/{MAX_COLS}]",
                callback_data=f"{prefix}_btnpos_{r}",
            )
    next_row = (max(rows.keys()) + 1) if rows else 0
    if next_row < MAX_ROWS:
        kb.button(
            text=f"🆕 New Row {next_row + 1}",
            callback_data=f"{prefix}_btnpos_{next_row}",
        )
    kb.button(text="❌ Cancel", callback_data=f"{prefix}_btn_start")
    kb.adjust(1)
    return kb.as_markup()


def _btn_manager_text(buttons: list) -> str:
    return (
        f"🔗 <b>Inline Buttons Manager</b>  ({len(buttons)}/{MAX_BUTTONS})\n\n"
        "<b>Layout preview:</b>\n"
        f"{_layout_preview(buttons)}\n\n"
        "<i>Tap 🗑 to remove a button, or add more.</i>"
    )


# ── Preview builder ───────────────────────────────────────────────────────────

async def _build_preview_data(user_id: int, bot=None):
    state = await fsm.get(user_id)
    if not state:
        return None
    meta         = state.get("meta", {})
    category     = state.get("category", "movie")
    custom_image = state.get("custom_image")
    settings     = await CosmicBotz.get_user_settings(user_id)
    watermark    = settings.get("watermark", "")
    logo_id      = settings.get("watermark_logo", "")
    tpl_body     = await CosmicBotz.get_active_template(user_id)
    caption      = _fmt.render(category, meta, template=tpl_body, user_settings=settings)

    if custom_image:
        thumb = await process_custom_thumbnail(
            custom_image,
            watermark=watermark,
            watermark_logo_id=logo_id,
            bot=bot,
        )
    else:
        thumb = await build_thumbnail(
            poster_url=meta.get("poster"),
            backdrop_url=meta.get("backdrop") or meta.get("banner"),
            watermark=watermark,
            watermark_logo_id=logo_id,
            bot=bot,
            meta={**meta, "_category": category},
        )

    prefix = CAT_TO_PREFIX[category]
    await fsm.update(user_id, {"caption": caption, "thumb": thumb, "step": "post"})
    return caption, thumb, prefix


async def _show_preview(cb: CallbackQuery):
    user_id = cb.from_user.id
    result  = await _build_preview_data(user_id, bot=cb.bot)
    if not result:
        try:
            await cb.message.edit_text("❌ Session expired. Start again.")
        except Exception:
            await cb.message.answer("❌ Session expired. Start again.")
        return
    caption, thumb, prefix = result
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.bot.send_photo(
        chat_id=cb.message.chat.id,
        photo=BufferedInputFile(thumb, filename="thumb.jpg"),
        caption=caption,
        reply_markup=preview_kb(prefix),
    )


async def _show_preview_from_message(msg: Message, user_id: int):
    result = await _build_preview_data(user_id, bot=msg.bot)
    if not result:
        await msg.edit_text("❌ Session expired. Start again.")
        return
    caption, thumb, prefix = result
    try:
        await msg.delete()
    except Exception:
        pass
    await msg.bot.send_photo(
        chat_id=msg.chat.id,
        photo=BufferedInputFile(thumb, filename="thumb.jpg"),
        caption=caption,
        reply_markup=preview_kb(prefix),
    )


# ── Search ────────────────────────────────────────────────────────────────────

async def _search(message: Message, category: str):
    allowed, reason = await check_mode(message.from_user.id)
    if not allowed:
        await message.answer(reason)
        return
    query = extract_query(message.text)
    if not query:
        await message.answer(
            f"<b>Usage:</b> <code>/{category} title</code>\n"
            f"<b>Example:</b> <code>/{category} {EXAMPLES[category]}</code>"
        )
        return
    msg = await message.answer(f"🔍 Searching <b>{query}</b>...")
    search_fn, _, _ = FETCHERS[category]
    try:
        results = await search_fn(query)
    except Exception as e:
        logger.error(f"Search [{category}] error: {e}")
        results = []
    if not results:
        await msg.edit_text(
            f"❌ No results for <b>{query}</b>.\nTry a different spelling or shorter title."
        )
        return
    prefix = CAT_TO_PREFIX[category]
    await fsm.set(message.from_user.id, {"category": category, "step": "select"})
    await msg.edit_text(
        f"🔎 <b>{len(results)} results</b> for <b>{query}</b> — choose one:",
        reply_markup=search_kb(results, prefix),
    )


@router.message(Command("movie", "tvshow", "anime", "manhwa"))
async def cmd_category(message: Message):
    raw      = message.text.lstrip("/").split()[0]
    category = raw.split("@")[0].lower()
    if category not in FETCHERS:
        return
    await _search(message, category)


# ── Select ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_select_(\d+)$"))
async def cb_select(cb: CallbackQuery):
    await cb.answer()
    # ✅ Fixed: was using `message` instead of `cb`
    allowed, reason = await check_mode(cb.from_user.id)
    if not allowed:
        await cb.message.answer(reason)
        return
    parts      = cb.data.split("_select_")
    raw_prefix = parts[0]
    item_id    = int(parts[1])
    category   = PREFIX_TO_CAT.get(raw_prefix)
    if not category:
        return
    _, detail_fn, _ = FETCHERS[category]
    await cb.message.edit_text("⏳ Fetching details...")
    try:
        meta = await detail_fn(item_id)
    except Exception as e:
        logger.error(f"Detail [{category}] {item_id}: {e}")
        meta = None
    if not meta:
        await cb.message.edit_text("❌ Could not fetch details. Please try again.")
        return
    await fsm.set(cb.from_user.id, {"category": category, "meta": meta, "step": "thumbnail"})
    await cb.message.edit_text(
        f"🖼 <b>{meta.get('title', 'Unknown')}</b> ready!\n\n"
        "📸 Send a <b>custom thumbnail</b> or tap <b>Skip</b> to use auto poster.",
        reply_markup=thumbnail_kb(CAT_TO_PREFIX[category]),
    )


# ── Thumbnail ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_thumb_skip$"))
async def cb_skip_thumb(cb: CallbackQuery):
    await cb.answer()
    await fsm.update(cb.from_user.id, {"step": "preview", "custom_image": None})
    await cb.message.edit_text("⏳ Building preview...")
    await _show_preview(cb)


@router.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    state   = await fsm.get(user_id)
    if not state:
        return
    step = state.get("step", "")

    # ── Logo watermark upload ─────────────────────────────────────────────────
    if step == "cfg_wm_logo":
        file_id = message.photo[-1].file_id
        await CosmicBotz.update_user_settings(user_id, {"watermark_logo": file_id})
        await fsm.clear(user_id)
        await message.answer(
            "✅ <b>Logo watermark saved!</b>\n\n"
            "It will appear on your thumbnails automatically.\n"
            "Go to /settings → Logo Watermark to remove it anytime."
        )
        return

    # ── Custom thumbnail upload ───────────────────────────────────────────────
    if step != "thumbnail":
        return
    wait = await message.answer("✅ Thumbnail received! Building preview...")
    try:
        file = await message.bot.get_file(message.photo[-1].file_id)
        buf  = io.BytesIO()
        await message.bot.download_file(file.file_path, destination=buf)
        await fsm.update(user_id, {"step": "preview", "custom_image": buf.getvalue()})
        await _show_preview_from_message(wait, user_id)
    except Exception as e:
        logger.error(f"Photo download error: {e}")
        await wait.edit_text("❌ Failed to process image. Try again or tap Skip.")


# ── Post to channel ───────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_post_channel$"))
async def cb_post_channel(cb: CallbackQuery):
    await cb.answer()
    uid   = cb.from_user.id
    state = await fsm.get(uid)
    if not state or not state.get("thumb"):
        await cb.answer("❌ Session expired. Generate again.", show_alert=True)
        return
    settings = await CosmicBotz.get_user_settings(uid)
    channel  = settings.get("channel_id")
    if not channel:
        await cb.answer("⚠️ No channel set! Go to /settings → Channel.", show_alert=True)
        return
    try:
        await cb.bot.send_photo(
            chat_id=channel,
            photo=BufferedInputFile(state["thumb"], filename="thumb.jpg"),
            caption=state["caption"],
        )
        await CosmicBotz.increment_post_count(uid)
        await fsm.clear(uid)
        await cb.answer("✅ Posted to channel!", show_alert=True)
        try:
            await cb.message.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Post failed: {e}")
        await cb.answer(f"❌ {e}", show_alert=True)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_post_direct$"))
async def cb_post_direct(cb: CallbackQuery):
    await cb_post_channel(cb)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_post_copy$"))
async def cb_copy(cb: CallbackQuery):
    await cb.answer()
    state = await fsm.get(cb.from_user.id)
    if not state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    await cb.message.answer(f"📋 <b>Caption:</b>\n\n{state.get('caption', '')}")
    await CosmicBotz.increment_post_count(cb.from_user.id)


# ── Template ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_change_tpl$"))
async def cb_change_tpl(cb: CallbackQuery):
    await cb.answer()
    state = await fsm.get(cb.from_user.id)
    if not state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    templates = await CosmicBotz.list_user_templates(cb.from_user.id)
    prefix    = CAT_TO_PREFIX[state.get("category", "movie")]
    await cb.message.edit_caption(
        caption="📄 <b>Select a Template:</b>",
        reply_markup=template_kb(templates, prefix),
    )


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_tpl_(.+)$"))
async def cb_tpl_pick(cb: CallbackQuery):
    await cb.answer()
    uid      = cb.from_user.id
    tpl_name = cb.data.split("_tpl_", 1)[1]
    if tpl_name == "default":
        await CosmicBotz.update_user_settings(uid, {"active_template": "default"})
    else:
        tpl = await CosmicBotz.get_template(uid, tpl_name)
        if tpl:
            await CosmicBotz.update_user_settings(uid, {"active_template": tpl_name})
        else:
            await cb.answer("Template not found.", show_alert=True)
            return
    await _show_preview(cb)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_back_preview$"))
async def cb_back_preview(cb: CallbackQuery):
    await cb.answer()
    await _show_preview(cb)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_redo_thumb$"))
async def cb_redo_thumb(cb: CallbackQuery):
    await cb.answer()
    state = await fsm.get(cb.from_user.id)
    if not state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    await fsm.update(cb.from_user.id, {"step": "thumbnail"})
    await cb.message.edit_caption(
        caption="📸 Send a new thumbnail or tap Skip:",
        reply_markup=thumbnail_kb(CAT_TO_PREFIX[state.get("category", "movie")]),
    )


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_cancel$"))
async def cb_cancel(cb: CallbackQuery):
    await cb.answer("Cancelled.")
    await fsm.clear(cb.from_user.id)
    try:
        await cb.message.delete()
    except Exception:
        pass


# ── Button flow ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_btn_start$"))
async def cb_btn_start(cb: CallbackQuery):
    await cb.answer()
    state = await fsm.get(cb.from_user.id)
    if not state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    buttons = state.get("buttons", [])
    prefix  = CAT_TO_PREFIX[state.get("category", "movie")]
    kb      = button_manage_kb(prefix, buttons) if buttons else add_button_start_kb(prefix)
    try:
        await cb.message.edit_caption(caption=_btn_manager_text(buttons), reply_markup=kb)
    except Exception:
        await cb.message.edit_text(_btn_manager_text(buttons), reply_markup=kb)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_btn_add$"))
async def cb_btn_add(cb: CallbackQuery):
    await cb.answer()
    state = await fsm.get(cb.from_user.id)
    if not state:
        return
    if len(state.get("buttons", [])) >= MAX_BUTTONS:
        await cb.answer(f"⚠️ Max {MAX_BUTTONS} buttons reached.", show_alert=True)
        return
    await fsm.update(cb.from_user.id, {"step": "btn_name"})
    prompt = (
        "🏷 <b>Step 1 of 3 — Button Label</b>\n\n"
        "Send the <b>text</b> for your button.\n\n"
        "<b>Examples:</b>\n"
        "▶️ Watch Now\n"
        "📖 Read Online\n"
        "🎬 Trailer\n"
        "⭐ Rate It\n"
        "🔔 Join Channel\n\n"
        "<i>Emojis, fancy text, symbols — all allowed!</i>"
    )
    try:
        await cb.message.edit_caption(caption=prompt, reply_markup=None)
    except Exception:
        await cb.message.edit_text(prompt, reply_markup=None)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_btn_del_(\d+)$"))
async def cb_btn_delete(cb: CallbackQuery):
    await cb.answer()
    uid     = cb.from_user.id
    idx     = int(cb.data.split("_btn_del_")[1])
    state   = await fsm.get(uid)
    if not state:
        return
    buttons = list(state.get("buttons", []))
    if 0 <= idx < len(buttons):
        removed = buttons.pop(idx)
        await fsm.update(uid, {"buttons": buttons})
        await cb.answer(f"🗑 Removed: {removed['text']}")
    prefix = CAT_TO_PREFIX[state.get("category", "movie")]
    kb     = button_manage_kb(prefix, buttons) if buttons else add_button_start_kb(prefix)
    try:
        await cb.message.edit_caption(caption=_btn_manager_text(buttons), reply_markup=kb)
    except Exception:
        await cb.message.edit_text(_btn_manager_text(buttons), reply_markup=kb)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_btn_defaults$"))
async def cb_btn_defaults(cb: CallbackQuery):
    """Show pre-built button sets."""
    await cb.answer()
    uid   = cb.from_user.id
    state = await fsm.get(uid)
    if not state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    category   = state.get("category", "movie")
    prefix     = CAT_TO_PREFIX[category]
    settings   = await CosmicBotz.get_user_settings(uid)
    saved_btns = settings.get("default_buttons", [])

    saved_preview = ""
    if saved_btns:
        saved_preview = "\n\n<b>Your saved defaults:</b>\n" + "\n".join(
            f"  • {b['text']}" for b in saved_btns
        )

    text = (
        "⚙️ <b>Default Button Sets</b>\n\n"
        "Pick a preset or use your saved defaults."
        + saved_preview
    )
    kb = default_buttons_kb(prefix, category)

    if saved_btns:
        builder = InlineKeyboardBuilder()
        builder.button(text="⭐ Use My Saved Defaults", callback_data=f"{prefix}_dflbtn_saved")
        for row in kb.inline_keyboard:
            for btn in row:
                if btn.callback_data:
                    builder.button(text=btn.text, callback_data=btn.callback_data)
        builder.adjust(1)
        kb = builder.as_markup()

    try:
        await cb.message.edit_caption(caption=text, reply_markup=kb)
    except Exception:
        await cb.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_dflbtn_(.+)$"))
async def cb_apply_default_buttons(cb: CallbackQuery):
    """Apply a preset button set."""
    await cb.answer()
    uid      = cb.from_user.id
    state    = await fsm.get(uid)
    if not state:
        return
    category = state.get("category", "movie")
    prefix   = CAT_TO_PREFIX[category]
    action   = cb.data.split("_dflbtn_", 1)[1]
    settings = await CosmicBotz.get_user_settings(uid)
    channel  = settings.get("channel_id", "")

    watch_label = "📖 Read Now" if category == "manhwa" else "▶️ Watch Now"
    watch_url   = channel if channel else "https://t.me/"

    presets = {
        "watch_dl": [
            {"text": watch_label,       "url": watch_url,                 "row": 0},
            {"text": "📥 Download",     "url": watch_url,                 "row": 0},
        ],
        "watch": [
            {"text": watch_label,       "url": watch_url,                 "row": 0},
        ],
        "dl": [
            {"text": "📥 Download",     "url": watch_url,                 "row": 0},
        ],
        "read_rate": [
            {"text": "📖 Read Now",     "url": watch_url,                 "row": 0},
            {"text": "⭐ Rate It",      "url": "https://myanimelist.net", "row": 0},
        ],
        "join_watch": [
            {"text": "🔔 Join Channel", "url": watch_url,                 "row": 0},
            {"text": watch_label,       "url": watch_url,                 "row": 1},
        ],
        "clear":  [],
        "saved":  settings.get("default_buttons", []),
    }

    buttons = presets.get(action, [])
    await fsm.update(uid, {"buttons": buttons, "step": "post"})
    kb = button_manage_kb(prefix, buttons) if buttons else add_button_start_kb(prefix)
    try:
        await cb.message.edit_caption(caption=_btn_manager_text(buttons), reply_markup=kb)
    except Exception:
        await cb.message.edit_text(_btn_manager_text(buttons), reply_markup=kb)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_btn_loadset$"))
async def cb_btn_loadset(cb: CallbackQuery):
    """Show user's saved button sets to pick from."""
    await cb.answer()
    uid   = cb.from_user.id
    state = await fsm.get(uid)
    if not state:
        return
    sets   = await CosmicBotz.list_button_sets(uid)
    prefix = CAT_TO_PREFIX[state.get("category", "movie")]
    if not sets:
        await cb.answer(
            "No saved button sets yet.\nUse /buttonsets to create one.",
            show_alert=True,
        )
        return
    kb = InlineKeyboardBuilder()
    for i, bs in enumerate(sets):
        count = len(bs.get("buttons", []))
        kb.button(
            text=f"🔗 {bs['name']}  ({count} btns)",
            callback_data=f"{prefix}_btn_applysets_{i}",
        )
    kb.button(text="🔙 Back", callback_data=f"{prefix}_btn_start")
    kb.adjust(1)
    try:
        await cb.message.edit_caption(
            caption="🔗 <b>Pick a Button Set</b>\n\nChoose a saved set to apply:",
            reply_markup=kb.as_markup(),
        )
    except Exception:
        await cb.message.edit_text(
            "🔗 <b>Pick a Button Set</b>\n\nChoose a saved set to apply:",
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_btn_applysets_(\d+)$"))
async def cb_btn_applyset(cb: CallbackQuery):
    """Apply chosen button set to current post."""
    await cb.answer()
    uid   = cb.from_user.id
    idx   = int(cb.data.split("_btn_applysets_")[1])
    state = await fsm.get(uid)
    if not state:
        return
    sets = await CosmicBotz.list_button_sets(uid)
    if idx >= len(sets):
        await cb.answer("Set not found.", show_alert=True)
        return
    buttons  = list(sets[idx].get("buttons", []))
    category = state.get("category", "movie")
    prefix   = CAT_TO_PREFIX[category]
    await fsm.update(uid, {"buttons": buttons, "step": "post"})
    await cb.answer(f"✅ Applied: {sets[idx]['name']}", show_alert=True)
    kb = button_manage_kb(prefix, buttons) if buttons else add_button_start_kb(prefix)
    try:
        await cb.message.edit_caption(caption=_btn_manager_text(buttons), reply_markup=kb)
    except Exception:
        await cb.message.edit_text(_btn_manager_text(buttons), reply_markup=kb)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_btnpos_(\d+)$"))
async def cb_btn_position(cb: CallbackQuery):
    """User chose which row — finalize button and return to manager."""
    await cb.answer()
    uid   = cb.from_user.id
    row   = int(cb.data.split("_btnpos_")[1])
    state = await fsm.get(uid)
    if not state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    pending_name = state.get("pending_btn_name")
    pending_url  = state.get("pending_btn_url")
    if not pending_name or not pending_url:
        await cb.answer("❌ Button data lost, please start again.", show_alert=True)
        return
    buttons  = list(state.get("buttons", []))
    buttons.append({"text": pending_name, "url": pending_url, "row": row})
    category = state.get("category", "movie")
    prefix   = CAT_TO_PREFIX[category]
    await fsm.update(uid, {
        "step":             "post",
        "buttons":          buttons,
        "pending_btn_name": None,
        "pending_btn_url":  None,
    })
    await cb.message.edit_text(
        _btn_manager_text(buttons),
        reply_markup=button_manage_kb(prefix, buttons),
    )


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_btn_done$"))
async def cb_btn_done(cb: CallbackQuery):
    await cb.answer()
    uid   = cb.from_user.id
    state = await fsm.get(uid)
    if not state or not state.get("thumb"):
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    settings = await CosmicBotz.get_user_settings(uid)
    channel  = settings.get("channel_id")
    if not channel:
        await cb.answer("⚠️ No channel set! Use /settings first.", show_alert=True)
        return
    buttons = state.get("buttons", [])
    try:
        await cb.bot.send_photo(
            chat_id=channel,
            photo=BufferedInputFile(state["thumb"], filename="thumb.jpg"),
            caption=state["caption"],
            reply_markup=build_post_keyboard(buttons),
        )
        await CosmicBotz.increment_post_count(uid)
        await fsm.clear(uid)
        note = f" with {len(buttons)} button(s)" if buttons else ""
        await cb.answer(f"✅ Posted{note}!", show_alert=True)
        try:
            await cb.message.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Post with buttons failed: {e}")
        await cb.answer(f"❌ {e}", show_alert=True)


# ── Single text handler ───────────────────────────────────────────────────────

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_input(message: Message):
    uid   = message.from_user.id
    state = await fsm.get(uid)
    if not state:
        return
    step = state.get("step", "")
    text = message.text.strip()

    # ── Post button flow ──────────────────────────────────────────────────────

    if step == "btn_name":
        if len(text) > 64:
            await message.answer("⚠️ Label too long (max 64 chars). Try again:")
            return
        await fsm.update(uid, {"step": "btn_url", "pending_btn_name": text})
        await message.answer(
            f"🔗 <b>Step 2 of 3 — Button URL</b>\n\n"
            f"Label: <b>{text}</b>\n\n"
            "Now send the <b>URL</b>:\n\n"
            "<code>https://t.me/yourchannel</code>\n"
            "<code>https://youtube.com/watch?v=...</code>"
        )

    elif step == "btn_url":
        if not (text.startswith("http://") or text.startswith("https://")):
            await message.answer("⚠️ Must start with <code>https://</code> — try again:")
            return
        await fsm.update(uid, {"step": "btn_pos", "pending_btn_url": text})
        buttons  = state.get("buttons", [])
        category = state.get("category", "movie")
        prefix   = CAT_TO_PREFIX[category]
        preview  = _layout_preview(buttons) if buttons else "<i>This will be the first button.</i>"
        await message.answer(
            f"📐 <b>Step 3 of 3 — Choose Row</b>\n\n"
            f"Label: <b>{state.get('pending_btn_name')}</b>\n"
            f"URL: <code>{text[:50]}{'...' if len(text) > 50 else ''}</code>\n\n"
            f"<b>Current layout:</b>\n{preview}\n\n"
            "Which row should this button go in?",
            reply_markup=_position_kb(prefix, buttons),
        )

    # ── Settings flow ─────────────────────────────────────────────────────────

    elif step == "cfg_watermark":
        await CosmicBotz.upsert_user(uid, "", "")
        if text.lower() == "clear":
            await CosmicBotz.update_user_settings(uid, {"watermark": ""})
            await message.answer("✅ Watermark cleared.")
        else:
            await CosmicBotz.update_user_settings(uid, {"watermark": text})
            await message.answer(f"✅ Watermark set to <code>{text}</code>")
        await fsm.clear(uid)

    elif step == "cfg_channel":
        if not (text.startswith("@") or text.lstrip("-").isdigit()):
            await message.answer("❌ Use <code>@channel</code> or numeric ID. Try again:")
            return
        await CosmicBotz.upsert_user(uid, "", "")
        await CosmicBotz.update_user_settings(uid, {"channel_id": text})
        await message.answer(
            f"✅ Channel linked: <code>{text}</code>\n"
            "Make sure the bot is admin in that channel!"
        )
        await fsm.clear(uid)

    elif step == "cfg_defbtn_name":
        if text.lower() == "clear":
            await CosmicBotz.update_user_settings(uid, {"default_buttons": []})
            await message.answer("✅ Default buttons cleared.")
            await fsm.clear(uid)
            return
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 2:
            await message.answer("❌ Format: <code>Name | https://url | row</code>")
            return
        btn_text = parts[0]
        btn_url  = parts[1]
        btn_row  = int(parts[2]) - 1 if len(parts) > 2 and parts[2].isdigit() else 0
        if not btn_url.startswith("http"):
            await message.answer("❌ URL must start with https://")
            return
        s       = await CosmicBotz.get_user_settings(uid)
        dflbtns = list(s.get("default_buttons", []))
        dflbtns.append({"text": btn_text, "url": btn_url, "row": btn_row})
        await CosmicBotz.update_user_settings(uid, {"default_buttons": dflbtns})
        await message.answer(
            f"✅ Default button added: <b>{btn_text}</b>\n"
            "Send another or use /settings to finish."
        )

    # ── Button set creation flow ──────────────────────────────────────────────

    elif step == "bset_name":
        if " " in text or len(text) > 32:
            await message.answer("❌ No spaces, max 32 chars. Try again:")
            return
        await fsm.update(uid, {"step": "bset_btn_name", "bset_name": text, "bset_buttons": []})
        await message.answer(
            f"✅ Name: <b>{text}</b>\n\n"
            "Now add your first button.\n"
            "Send the <b>button label</b>:\n\n"
            "▶️ Watch Now\n📥 Download\n🔔 Join Channel"
        )

    elif step == "bset_btn_name":
        if len(text) > 64:
            await message.answer("⚠️ Max 64 chars. Try again:")
            return
        await fsm.update(uid, {"step": "bset_btn_url", "bset_pending_name": text})
        await message.answer(
            f"🔗 <b>Button URL</b>\n\nLabel: <b>{text}</b>\n\nSend the URL:"
        )

    elif step == "bset_btn_url":
        if not (text.startswith("http://") or text.startswith("https://")):
            await message.answer("⚠️ Must start with https:// — try again:")
            return
        await fsm.update(uid, {"step": "bset_btn_row", "bset_pending_url": text})
        fresh = await fsm.get(uid)
        btns  = fresh.get("bset_buttons", [])
        rows: dict = {}
        for b in btns:
            rows.setdefault(b.get("row", 0), []).append(b["text"])
        preview = (
            "\n".join(f"  Row {r+1}: " + "  |  ".join(rows[r]) for r in sorted(rows))
            or "  <i>First button</i>"
        )
        kb = InlineKeyboardBuilder()
        for r in range(4):
            existing = rows.get(r, [])
            if len(existing) < 4:
                label = f"Row {r+1}" + (f"  [{len(existing)} here]" if existing else "  [empty]")
                kb.button(text=label, callback_data=f"bset_row:{r}")
        kb.adjust(2)
        await message.answer(
            f"📐 <b>Which row?</b>\n\n<b>Current:</b>\n{preview}",
            reply_markup=kb.as_markup(),
        )

    elif step == "bset_edit":
        if len(text) > 64:
            await message.answer("⚠️ Max 64 chars. Try again:")
            return
        await fsm.update(uid, {"step": "bset_btn_url", "bset_pending_name": text})
        await message.answer(f"🔗 URL for <b>{text}</b>:")

    # ── Template flow ─────────────────────────────────────────────────────────

    elif step == "tpl_name":
        if " " in text or len(text) > 32:
            await message.answer("❌ No spaces, max 32 chars. Try again:")
            return
        await fsm.update(uid, {"step": "tpl_body", "tpl_name": text})
        await message.answer(
            f"✅ Name: <b>{text}</b>\n\n"
            "Now send the <b>template body</b>.\n"
            "Must include <code>{title}</code>."
        )

    elif step == "tpl_body":
        if "{title}" not in text:
            await message.answer("⚠️ Must contain <code>{title}</code>. Try again:")
            return
        name = state.get("tpl_name", "unnamed")
        await CosmicBotz.save_template(uid, name, text)
        await CosmicBotz.update_user_settings(uid, {"active_template": name})
        await fsm.clear(uid)
        await message.answer(f"✅ <b>Template '{name}' saved and activated!</b>")

    elif step == "adm_broadcast":
        from routers.admin import do_broadcast
        await do_broadcast(message, text)


# ───────────────────────────────────────────────────────────
    elif step == "adm_userinfo":
        if not text.lstrip("-").isdigit():
            await message.answer("❌ Send a valid numeric user ID:")
            return
        await fsm.clear(uid)
        from routers.admin import _send_userinfo
        await _send_userinfo(message, int(text))

    elif step == "adm_ban":
        if not text.isdigit():
            await message.answer("❌ Send a valid numeric user ID:")
            return
        await fsm.clear(uid)
        target_id = int(text)
        await CosmicBotz.ban_user(target_id)
        await message.answer(f"⛔ User <code>{target_id}</code> banned.")
        try:
            await message.bot.send_message(target_id, "⛔ You have been <b>banned</b> from this bot.")
        except Exception:
            pass

    elif step == "adm_unban":
        if not text.isdigit():
            await message.answer("❌ Send a valid numeric user ID:")
            return
        await fsm.clear(uid)
        target_id = int(text)
        await CosmicBotz.unban_user(target_id)
        await message.answer(f"✅ User <code>{target_id}</code> unbanned.")
        try:
            await message.bot.send_message(target_id, "✅ You have been <b>unbanned</b>. Welcome back!")
        except Exception:
            pass

    elif step == "adm_addpremium":
        if not text.isdigit():
            await message.answer("❌ Send a valid numeric user ID:")
            return
        await fsm.clear(uid)
        target_id = int(text)
        await CosmicBotz.set_premium(target_id, True)
        await message.answer(f"⭐ Premium granted to <code>{target_id}</code>.")
        try:
            await message.bot.send_message(target_id, "🎉 <b>You've been upgraded to ⭐ Premium!</b>\nEnjoy unlimited access.")
        except Exception:
            pass

    elif step == "adm_revoke":
        if not text.isdigit():
            await message.answer("❌ Send a valid numeric user ID:")
            return
        await fsm.clear(uid)
        target_id = int(text)
        await CosmicBotz.set_premium(target_id, False)
        await message.answer(f"✅ Premium revoked for <code>{target_id}</code>.")
        try:
            await message.bot.send_message(target_id, "ℹ️ Your <b>Premium</b> access has been revoked.")
        except Exception:
            pass

    elif step == "adm_maint_msg":
        await fsm.clear(uid)
        await CosmicBotz.set_maintenance_message(text)
        await message.answer(
            f"✅ <b>Maintenance message saved!</b>\n\n"
            f"<i>{text}</i>\n\n"
            "Use <code>/mode maintenance</code> to activate it."
        )


