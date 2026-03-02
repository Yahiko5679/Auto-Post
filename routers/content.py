import io
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from PIL import Image, ImageDraw, ImageFont

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
    ask_add_buttons_kb, finish_adding_kb, confirm_post_with_buttons_kb,
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


def create_action_button_overlay(category: str, base_img: Image.Image) -> Image.Image:
    img = base_img.copy().convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")

    text = "Read Now" if category == "manhwa" else "Watch Now"

    try:
        font = ImageFont.truetype("arial.ttf", 48)  # change path if you have better font
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    padding_x, padding_y = 32, 16
    btn_w = text_w + padding_x * 2
    btn_h = text_h + padding_y * 2
    radius = btn_h // 2

    margin = 40
    x = img.width - btn_w - margin
    y = img.height - btn_h - margin

    draw.rounded_rectangle(
        [x, y, x + btn_w, y + btn_h],
        radius=radius,
        fill=(0, 0, 0, 160),
        outline=(255, 255, 255, 100),
        width=2
    )

    text_x = x + (btn_w - text_w) // 2
    text_y = y + (btn_h - text_h) // 2
    draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))

    return img.convert("RGB")


async def _build_preview_data(user_id: int):
    state = await fsm.get(user_id)
    if not state:
        return None

    meta = state.get("meta", {})
    category = state.get("category", "movie")
    custom_image = state.get("custom_image")
    settings = await CosmicBotz.get_user_settings(user_id)
    watermark = settings.get("watermark", "")
    tpl_body = await CosmicBotz.get_active_template(user_id)

    caption = _fmt.render(category, meta, template=tpl_body, user_settings=settings)

    if custom_image:
        thumb_bytes = await process_custom_thumbnail(custom_image, watermark=watermark)
        if isinstance(thumb_bytes, bytes):
            thumb_pil = Image.open(io.BytesIO(thumb_bytes))
        else:
            thumb_pil = thumb_bytes  # assume already PIL Image
    else:
        thumb_bytes = await build_thumbnail(
            poster_url=meta.get("poster"),
            backdrop_url=meta.get("backdrop") or meta.get("banner"),
            watermark=watermark,
            meta={**meta, "_category": category},
        )
        thumb_pil = Image.open(io.BytesIO(thumb_bytes))

    thumb_pil = create_action_button_overlay(category, thumb_pil)

    thumb_io = io.BytesIO()
    thumb_pil.save(thumb_io, format="JPEG", quality=95)
    thumb = thumb_io.getvalue()

    prefix = CAT_TO_PREFIX[category]
    await fsm.update(user_id, {"caption": caption, "thumb": thumb, "step": "post"})
    return caption, thumb, prefix


def build_post_keyboard(buttons_data: list[dict]) -> InlineKeyboardMarkup | None:
    if not buttons_data:
        return None

    builder = InlineKeyboardBuilder()
    for btn in buttons_data:
        text = btn.get("text", "Button")
        if btn.get("url"):
            builder.button(text=text, url=btn["url"])
        elif btn.get("callback_data"):
            builder.button(text=text, callback_data=btn["callback_data"])
    builder.adjust(3)
    return builder.as_markup()


async def _do_post_to_channel(event: CallbackQuery | Message, state: dict):
    if isinstance(event, CallbackQuery):
        user_id = event.from_user.id
        bot = event.bot
        answer = event.answer
        delete = event.message.delete
    else:
        user_id = event.from_user.id
        bot = event.bot
        answer = event.answer
        delete = lambda: None

    settings = await CosmicBotz.get_user_settings(user_id)
    channel = settings.get("channel_id")

    if not channel:
        await answer("⚠️ No channel set!", show_alert=True)
        return

    try:
        photo = BufferedInputFile(state["thumb"], filename="thumb.jpg")
        kb = build_post_keyboard(state.get("buttons", []))

        await bot.send_photo(
            chat_id=channel,
            photo=photo,
            caption=state["caption"],
            reply_markup=kb
        )
        await CosmicBotz.increment_post_count(user_id)
        await fsm.clear(user_id)

        msg = "✅ Posted to channel!" + (" with buttons" if kb else "")
        await answer(msg, show_alert=True)
        if isinstance(event, CallbackQuery):
            await delete()
    except Exception as e:
        logger.error(f"Post failed: {e}")
        await answer(f"❌ Failed: {str(e)}", show_alert=True)


# ────────────────────────────────────────────────
#                  HANDLERS
# ────────────────────────────────────────────────

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


@router.message(Command("movie", "tvshow", "anime", "manhwa"))
async def cmd_category(message: Message):
    category = message.text.lstrip("/").split()[0]
    await _search(message, category)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_select_(\d+)$"))
async def cb_select(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    parts = cb.data.split("_select_")
    raw_prefix = parts[0]
    item_id = int(parts[1])
    category = PREFIX_TO_CAT[raw_prefix]
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
    state = await fsm.get(user_id)
    if not state or state.get("step") != "thumbnail":
        return
    wait = await message.answer("✅ Thumbnail received! Building preview...")
    file = await message.bot.get_file(message.photo[-1].file_id)
    buf = io.BytesIO()
    await message.bot.download_file(file.file_path, destination=buf)
    photo_bytes = buf.getvalue()
    await fsm.update(user_id, {"step": "preview", "custom_image": photo_bytes})
    await _show_preview_from_message(wait, user_id)


async def _show_preview(cb: CallbackQuery):
    user_id = cb.from_user.id
    result = await _build_preview_data(user_id)
    if not result:
        await cb.message.edit_text("❌ Session expired. Please start again.")
        return
    caption, thumb, prefix = result

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
    user_id = cb.from_user.id
    state = await fsm.get(user_id)

    if not state or "thumb" not in state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return

    prefix = CAT_TO_PREFIX[state.get("category", "movie")]

    if state.get("buttons"):
        await _show_buttons_preview(cb, state, prefix)
        return

    caption = cb.message.caption or ""
    await cb.message.edit_caption(
        caption=caption + "\n\n<b>Add inline buttons?</b>",
        reply_markup=ask_add_buttons_kb(prefix)
    )


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_post_no_buttons$"))
async def cb_post_no_buttons(cb: CallbackQuery):
    await cb.answer()
    state = await fsm.get(cb.from_user.id)
    if not state:
        return
    await _do_post_to_channel(cb, state)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_add_buttons$"))
async def cb_start_adding_buttons(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    prefix = cb.data.split("_add_buttons")[0]

    state = await fsm.get(user_id) or {}
    await fsm.update(user_id, {
        "step": "adding_buttons",
        "buttons": state.get("buttons", [])
    })

    text = (
        "📎 <b>Add inline buttons</b>\n\n"
        "One per message:\n"
        "<code>Text | url:https://...</code>\n"
        "<code>Text | callback:some_data</code>\n\n"
        "Examples:\n"
        "<code>Trailer | url:https://youtu.be/...</code>\n"
        "<code>Like | callback:like_123</code>\n\n"
        "Finish → /done or button below"
    )

    await cb.message.edit_caption(caption=text, reply_markup=finish_adding_kb(prefix))


@router.message(F.text)
async def collect_button_line(message: Message):
    text = message.text.strip()

    # Skip if it looks like a command (prevents stealing /settings, /stats etc.)
    if text.lstrip().startswith("/"):
        return

    user_id = message.from_user.id
    state = await fsm.get(user_id)
    
    if not state or state.get("step") != "adding_buttons":
        return

    if "|" not in text:
        await message.reply("Format: <code>Text | url:https://...   or   Text | callback:...</code>")
        return

    btn_text, value_part = [p.strip() for p in text.split("|", 1)]
    btn = {"text": btn_text}

    if value_part.startswith("url:"):
        btn["url"] = value_part[4:].strip()
    elif value_part.startswith("callback:"):
        btn["callback_data"] = value_part[9:].strip()
    elif value_part.startswith(("http://", "https://")):
        btn["url"] = value_part
    else:
        await message.reply("Value must start with url: or callback: or be full http/https link.")
        return

    buttons = state.get("buttons", [])
    buttons.append(btn)
    await fsm.update(user_id, {"buttons": buttons})

    await message.reply(
        f"Added ({len(buttons)}):\n{text}\n\n"
        "Send next button or send /done"
    )


@router.message(Command("done"))
@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_finish_buttons$"))
async def finish_adding_buttons(event):
    is_cb = isinstance(event, CallbackQuery)
    user_id = event.from_user.id
    state = await fsm.get(user_id)

    if not state or state.get("step") != "adding_buttons":
        if is_cb:
            await event.answer("Not in button mode", show_alert=True)
        return

    prefix = CAT_TO_PREFIX[state.get("category", "movie")]

    if is_cb:
        await event.answer()

    buttons = state.get("buttons", [])
    photo = BufferedInputFile(state["thumb"], "thumb.jpg")
    caption = state["caption"] + ("\n\n<b>With buttons</b>" if buttons else "")
    kb = build_post_keyboard(buttons)
    confirm_kb = confirm_post_with_buttons_kb(prefix) if buttons else preview_kb(prefix)

    try:
        if is_cb:
            await event.message.delete()
    except:
        pass

    chat_id = event.message.chat.id if is_cb else event.chat.id
    sent = await event.bot.send_photo(
        chat_id=chat_id,
        photo=photo,
        caption=caption,
        reply_markup=confirm_kb
    )

    await fsm.update(user_id, {"preview_msg_id": sent.message_id})


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_confirm_post_buttons$"))
async def cb_confirm_post_buttons(cb: CallbackQuery):
    await cb.answer()
    state = await fsm.get(cb.from_user.id)
    if not state:
        await cb.answer("Session expired.", show_alert=True)
        return
    await _do_post_to_channel(cb, state)


# ────────────────────────────────────────────────
#  Original remaining handlers (unchanged)
# ────────────────────────────────────────────────

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
    state = await fsm.get(cb.from_user.id)
    if not state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    category = state.get("category", "movie")
    prefix = CAT_TO_PREFIX[category]
    templates = await CosmicBotz.list_user_templates(cb.from_user.id)
    await cb.message.edit_caption(
        caption="📄 <b>Select a Template:</b>",
        reply_markup=template_kb(templates, prefix),
    )


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_tpl_(.+)$"))
async def cb_tpl_pick(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
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
    state = await fsm.get(cb.from_user.id)
    if not state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    category = state.get("category", "movie")
    prefix = CAT_TO_PREFIX[category]
    await fsm.update(cb.from_user.id, {"step": "thumbnail"})
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