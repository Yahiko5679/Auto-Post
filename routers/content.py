import io
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import CosmicBotz
from fetchers.tmdb import TMDbFetcher
from fetchers.jikan import JikanFetcher
from fetchers.anilist import AniListFetcher
from formatter.engine import FormatEngine
from thumbnail.processor import build_thumbnail, process_custom_thumbnail
from utils.fsm import fsm
from utils.helpers import (
    extract_query,
    search_kb, thumbnail_kb, preview_kb, template_kb,
)

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
    "movie": "Inception", "tvshow": "Breaking Bad",
    "anime": "Attack on Titan", "manhwa": "Solo Leveling",
}
PREFIX_TO_CAT = {"movie": "movie", "tv": "tvshow", "anime": "anime", "manhwa": "manhwa"}
CAT_TO_PREFIX = {"movie": "movie", "tvshow": "tv", "anime": "anime", "manhwa": "manhwa"}


async def _search(message: Message, category: str):
    query = extract_query(message.text)
    if not query:
        await message.answer(
            f"<b>Usage:</b> <code>/{category} title</code>\n"
            f"<b>Example:</b> <code>/{category} {EXAMPLES[category]}</code>"
        )
        return
    msg = await message.answer(f"🔍 Searching <b>{query}</b>...")
    search_fn, _, prefix = FETCHERS[category]
    try:
        results = await search_fn(query)
    except Exception as e:
        logger.error(f"Search [{category}]: {e}")
        results = []
    if not results:
        await msg.edit_text("❌ No results found. Try a different title.")
        return
    await fsm.set(message.from_user.id, {"category": category, "step": "select"})
    await msg.edit_text(
        f"🔎 <b>{len(results)} results</b> for <b>{query}</b> — choose one:",
        reply_markup=search_kb(results, prefix),
    )


@router.message(Command("movie"))
async def cmd_movie(message: Message):
    await _search(message, "movie")

@router.message(Command("tvshow"))
async def cmd_tvshow(message: Message):
    await _search(message, "tvshow")

@router.message(Command("anime"))
async def cmd_anime(message: Message):
    await _search(message, "anime")

@router.message(Command("manhwa"))
async def cmd_manhwa(message: Message):
    await _search(message, "manhwa")


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_select_(\d+)$"))
async def cb_select(cb: CallbackQuery):
    await cb.answer()
    user_id    = cb.from_user.id
    parts      = cb.data.split("_select_")
    raw_prefix = parts[0]
    item_id    = int(parts[1])
    category   = PREFIX_TO_CAT[raw_prefix]
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

    await fsm.set(user_id, {"category": category, "meta": meta, "step": "thumbnail"})
    await cb.message.edit_text(
        f"🖼 <b>{meta['title']}</b> — details ready!\n\n"
        "📸 Send a <b>custom thumbnail</b> or tap <b>Skip</b> to use auto poster.",
        reply_markup=thumbnail_kb(CAT_TO_PREFIX[category]),
    )


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
    if not state or state.get("step") != "thumbnail":
        return
    wait = await message.answer("✅ Thumbnail received! Building preview...")
    file = await message.bot.get_file(message.photo[-1].file_id)
    buf  = io.BytesIO()
    await message.bot.download_file(file.file_path, destination=buf)
    photo_bytes = buf.getvalue()
    await fsm.update(user_id, {"step": "preview", "custom_image": photo_bytes})
    await _show_preview_from_message(wait, user_id)


async def _build_preview_data(user_id: int):
    """Build caption and thumbnail bytes. Returns (caption, thumb, prefix) or None."""
    state = await fsm.get(user_id)
    if not state:
        return None
    meta         = state.get("meta", {})
    category     = state.get("category", "movie")
    custom_image = state.get("custom_image")
    settings     = await CosmicBotz.get_user_settings(user_id)
    watermark    = settings.get("watermark", "")
    tpl_body     = await CosmicBotz.get_active_template(user_id)

    caption = _fmt.render(category, meta, template=tpl_body, user_settings=settings)

    if custom_image:
        thumb = await process_custom_thumbnail(custom_image, watermark=watermark)
    else:
        thumb = await build_thumbnail(
    poster_url=meta.get("poster"),
    backdrop_url=meta.get("backdrop") or meta.get("banner"),
    watermark=watermark,
    meta={**meta, "_category": category},
)

    prefix = CAT_TO_PREFIX[category]
    await fsm.update(user_id, {"caption": caption, "thumb": thumb, "step": "post"})
    return caption, thumb, prefix


async def _show_preview(cb: CallbackQuery):
    """Called from a callback — deletes old message and sends new photo."""
    user_id = cb.from_user.id
    result  = await _build_preview_data(user_id)
    if not result:
        await cb.message.edit_text("❌ Session expired. Please start again.")
        return
    caption, thumb, prefix = result

    # Delete the current message safely
    try:
        await cb.message.delete()
    except Exception:
        pass

    photo = BufferedInputFile(thumb, filename="thumb.jpg")
    await cb.bot.send_photo(
        chat_id=cb.message.chat.id,
        photo=photo,
        caption=caption,
        reply_markup=preview_kb(prefix),
    )


async def _show_preview_from_message(msg: Message, user_id: int):
    """Called from a message handler."""
    result = await _build_preview_data(user_id)
    if not result:
        await msg.edit_text("❌ Session expired. Please start again.")
        return
    caption, thumb, prefix = result

    try:
        await msg.delete()
    except Exception:
        pass

    photo = BufferedInputFile(thumb, filename="thumb.jpg")
    await msg.bot.send_photo(
        chat_id=msg.chat.id,
        photo=photo,
        caption=caption,
        reply_markup=preview_kb(prefix),
    )


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_post_channel$"))
async def cb_post_channel(cb: CallbackQuery):
    await cb.answer()
    user_id  = cb.from_user.id
    state    = await fsm.get(user_id)

    if not state or not state.get("thumb"):
        await cb.answer("❌ Session expired. Generate the post again.", show_alert=True)
        return

    settings = await CosmicBotz.get_user_settings(user_id)
    channel  = settings.get("channel_id")

    if not channel:
        await cb.answer("⚠️ No channel set! Use /settings → Channel.", show_alert=True)
        return

    try:
        photo = BufferedInputFile(state["thumb"], filename="thumb.jpg")
        await cb.bot.send_photo(chat_id=channel, photo=photo, caption=state["caption"])
        await CosmicBotz.increment_post_count(user_id)
        await fsm.clear(user_id)
        await cb.answer("✅ Posted to channel!", show_alert=True)
        await cb.message.delete()
    except Exception as e:
        logger.error(f"Post to channel failed: {e}")
        await cb.answer(f"❌ Failed: {e}", show_alert=True)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_post_copy$"))
async def cb_copy(cb: CallbackQuery):
    await cb.answer()
    state = await fsm.get(cb.from_user.id)
    if not state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    await cb.message.answer(f"📋 <b>Caption:</b>\n\n{state.get('caption', '')}")
    await CosmicBotz.increment_post_count(cb.from_user.id)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_change_tpl$"))
async def cb_change_tpl(cb: CallbackQuery):
    await cb.answer()
    state     = await fsm.get(cb.from_user.id)
    if not state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    category  = state.get("category", "movie")
    prefix    = CAT_TO_PREFIX[category]
    templates = await CosmicBotz.list_user_templates(cb.from_user.id)
    # Edit caption of the photo message
    await cb.message.edit_caption(
        caption="📄 <b>Select a Template:</b>",
        reply_markup=template_kb(templates, prefix),
    )


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_tpl_(.+)$"))
async def cb_tpl_pick(cb: CallbackQuery):
    await cb.answer()
    user_id  = cb.from_user.id
    tpl_name = cb.data.split("_tpl_", 1)[1]
    if tpl_name == "default":
        await CosmicBotz.update_user_settings(user_id, {"active_template": "default"})
    else:
        tpl = await CosmicBotz.get_template(user_id, tpl_name)
        if tpl:
            await CosmicBotz.update_user_settings(user_id, {"active_template": tpl_name})
    await cb.answer("✅ Template applied!", show_alert=False)
    await _show_preview(cb)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_back_preview$"))
async def cb_back_preview(cb: CallbackQuery):
    await cb.answer()
    await _show_preview(cb)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_redo_thumb$"))
async def cb_redo_thumb(cb: CallbackQuery):
    await cb.answer()
    state    = await fsm.get(cb.from_user.id)
    if not state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    category = state.get("category", "movie")
    prefix   = CAT_TO_PREFIX[category]
    await fsm.update(cb.from_user.id, {"step": "thumbnail"})
    # edit_caption works on photo messages, edit_text does not
    await cb.message.edit_caption(
        caption="📸 Send a new thumbnail image or tap Skip:",
        reply_markup=thumbnail_kb(prefix),
    )


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_cancel$"))
async def cb_cancel(cb: CallbackQuery):
    await cb.answer("Cancelled.")
    await fsm.clear(cb.from_user.id)
    try:
        await cb.message.delete()
    except Exception:
        pass
