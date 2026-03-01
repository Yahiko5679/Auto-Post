"""
Content generation — /movie  /tvshow  /anime  /manhwa
Handles search → select → thumbnail → preview → post flow.
"""
import io
import logging
from pyrofork import Client, filters
from pyrofork.types import Message, CallbackQuery

from database.db import CosmicBotz
from fetchers.tmdb import TMDbFetcher
from fetchers.jikan import JikanFetcher
from fetchers.anilist import AniListFetcher
from formatter.engine import FormatEngine
from thumbnail.processor import build_thumbnail, process_custom_thumbnail
from utils.fsm import fsm
from utils.helpers import (
    track_user, banned_check, daily_limit_check,
    search_kb, thumbnail_kb, preview_kb, template_kb,
    post_to_channel, extract_query,
)

logger = logging.getLogger(__name__)

_tmdb    = TMDbFetcher()
_jikan   = JikanFetcher()
_anilist = AniListFetcher()
_fmt     = FormatEngine()

# category → (search_fn, detail_fn, cb_prefix)
FETCHERS = {
    "movie":  (_tmdb.search_movies,    _tmdb.get_movie,       "movie"),
    "tvshow": (_tmdb.search_tv,        _tmdb.get_tv,          "tv"),
    "anime":  (_jikan.search_anime,    _jikan.get_anime,      "anime"),
    "manhwa": (_anilist.search_manhwa, _anilist.get_manhwa,   "manhwa"),
}
EXAMPLES = {
    "movie": "Inception", "tvshow": "Breaking Bad",
    "anime": "Attack on Titan", "manhwa": "Solo Leveling",
}
# callback prefix → category
PREFIX_TO_CAT = {"movie": "movie", "tv": "tvshow", "anime": "anime", "manhwa": "manhwa"}


# ── Commands ──────────────────────────────────────────────────────────────────

async def _search(client: Client, message: Message, category: str):
    query = extract_query(message.text)
    if not query:
        await message.reply(
            f"**Usage:** `/{category} <title>`\n"
            f"**Example:** `/{category} {EXAMPLES[category]}`"
        )
        return

    msg = await message.reply(f"🔍 Searching **{query}**...")
    search_fn, _, prefix = FETCHERS[category]
    try:
        results = await search_fn(query)
    except Exception as e:
        logger.error(f"Search [{category}]: {e}")
        results = []

    if not results:
        await msg.edit("❌ No results found. Try a different title.")
        return

    await fsm.set(message.from_user.id, {"category": category, "step": "select"})
    await msg.edit(
        f"🔎 **{len(results)} results** for **{query}** — choose one:",
        reply_markup=search_kb(results, prefix),
    )


@Client.on_message(filters.command("movie") & filters.private)
@banned_check
@track_user
@daily_limit_check
async def cmd_movie(client, message):
    await _search(client, message, "movie")


@Client.on_message(filters.command("tvshow") & filters.private)
@banned_check
@track_user
@daily_limit_check
async def cmd_tvshow(client, message):
    await _search(client, message, "tvshow")


@Client.on_message(filters.command("anime") & filters.private)
@banned_check
@track_user
@daily_limit_check
async def cmd_anime(client, message):
    await _search(client, message, "anime")


@Client.on_message(filters.command("manhwa") & filters.private)
@banned_check
@track_user
@daily_limit_check
async def cmd_manhwa(client, message):
    await _search(client, message, "manhwa")


# ── Select result ─────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^(movie|tv|anime|manhwa)_select_(\d+)$"))
async def cb_select(client: Client, cb: CallbackQuery):
    await cb.answer()
    user_id    = cb.from_user.id
    raw_prefix = cb.data.split("_select_")[0]          # "movie" / "tv" / "anime" / "manhwa"
    item_id    = int(cb.data.split("_select_")[1])
    category   = PREFIX_TO_CAT[raw_prefix]
    _, detail_fn, prefix = FETCHERS[category]

    await cb.message.edit("⏳ Fetching details...")
    try:
        meta = await detail_fn(item_id)
    except Exception as e:
        logger.error(f"Detail [{category}] {item_id}: {e}")
        meta = None

    if not meta:
        await cb.message.edit("❌ Could not fetch details. Please try again.")
        return

    await fsm.set(user_id, {"category": category, "meta": meta, "step": "thumbnail"})
    await cb.message.edit(
        f"🖼 **{meta['title']}** — details ready!\n\n"
        "📸 Send a **custom thumbnail** or tap **Skip** to use the auto poster.",
        reply_markup=thumbnail_kb(prefix),
    )


# ── Thumbnail ─────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^(movie|tv|anime|manhwa)_thumb_skip$"))
async def cb_skip_thumb(client: Client, cb: CallbackQuery):
    await cb.answer()
    await fsm.update(cb.from_user.id, {"step": "preview", "custom_image": None})
    await _show_preview(client, cb.message, cb.from_user.id)


@Client.on_message(filters.photo & filters.private)
async def handle_photo(client: Client, message: Message):
    user_id = message.from_user.id
    state   = await fsm.get(user_id)
    if not state or state.get("step") != "thumbnail":
        return
    wait = await message.reply("✅ Thumbnail received! Building preview...")
    buf = await client.download_media(message.photo.file_id, in_memory=True)
    photo_bytes = bytes(buf.getbuffer()) if hasattr(buf, "getbuffer") else bytes(buf)
    await fsm.update(user_id, {"step": "preview", "custom_image": photo_bytes})
    await _show_preview(client, wait, user_id, edit=True)


# ── Preview builder ───────────────────────────────────────────────────────────

async def _show_preview(client: Client, msg, user_id: int, edit: bool = False):
    state = await fsm.get(user_id)
    if not state:
        return
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
        )

    prefix = {"movie": "movie", "tvshow": "tv", "anime": "anime", "manhwa": "manhwa"}[category]
    await fsm.update(user_id, {"caption": caption, "thumb": thumb, "step": "post"})

    try:
        await msg.delete()
    except Exception:
        pass
    await client.send_photo(
        chat_id=msg.chat.id,
        photo=io.BytesIO(thumb),
        caption=caption,
        reply_markup=preview_kb(prefix),
    )


# ── Post actions ──────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^(movie|tv|anime|manhwa)_post_channel$"))
async def cb_post_channel(client: Client, cb: CallbackQuery):
    await cb.answer()
    user_id  = cb.from_user.id
    state    = await fsm.get(user_id)
    settings = await CosmicBotz.get_user_settings(user_id)
    channel  = settings.get("channel_id")

    if not channel:
        await cb.answer("⚠️ No channel set! Go to /settings → Channel.", show_alert=True)
        return

    ok = await post_to_channel(client, channel, state["thumb"], state["caption"])
    if ok:
        await CosmicBotz.increment_post_count(user_id)
        await fsm.clear(user_id)
        await cb.answer("✅ Posted successfully!", show_alert=True)
        await cb.message.delete()
    else:
        await cb.answer("❌ Post failed — make sure bot is admin in the channel.", show_alert=True)


@Client.on_callback_query(filters.regex(r"^(movie|tv|anime|manhwa)_post_copy$"))
async def cb_copy(client: Client, cb: CallbackQuery):
    await cb.answer()
    state = await fsm.get(cb.from_user.id)
    await cb.message.reply(f"📋 **Caption:**\n\n{state.get('caption', '')}")
    await CosmicBotz.increment_post_count(cb.from_user.id)


# ── Template switcher ─────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^(movie|tv|anime|manhwa)_change_tpl$"))
async def cb_change_tpl(client: Client, cb: CallbackQuery):
    await cb.answer()
    user_id   = cb.from_user.id
    state     = await fsm.get(user_id)
    category  = state.get("category", "movie")
    prefix    = {"movie": "movie", "tvshow": "tv", "anime": "anime", "manhwa": "manhwa"}[category]
    templates = await CosmicBotz.list_user_templates(user_id)
    await cb.message.edit("📄 **Select a Template:**", reply_markup=template_kb(templates, prefix))


@Client.on_callback_query(filters.regex(r"^(movie|tv|anime|manhwa)_tpl_(.+)$"))
async def cb_tpl_pick(client: Client, cb: CallbackQuery):
    await cb.answer()
    user_id  = cb.from_user.id
    tpl_name = cb.data.split("_tpl_", 1)[1]
    if tpl_name == "default":
        await CosmicBotz.update_user_settings(user_id, {"active_template": "default"})
    else:
        tpl = await CosmicBotz.get_template(user_id, tpl_name)
        if tpl:
            await CosmicBotz.update_user_settings(user_id, {"active_template": tpl_name})
    await _show_preview(client, cb.message, user_id)


@Client.on_callback_query(filters.regex(r"^(movie|tv|anime|manhwa)_back_preview$"))
async def cb_back_preview(client: Client, cb: CallbackQuery):
    await cb.answer()
    await _show_preview(client, cb.message, cb.from_user.id)


# ── Redo thumbnail ────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^(movie|tv|anime|manhwa)_redo_thumb$"))
async def cb_redo_thumb(client: Client, cb: CallbackQuery):
    await cb.answer()
    user_id  = cb.from_user.id
    state    = await fsm.get(user_id)
    category = state.get("category", "movie")
    prefix   = {"movie": "movie", "tvshow": "tv", "anime": "anime", "manhwa": "manhwa"}[category]
    await fsm.update(user_id, {"step": "thumbnail"})
    await cb.message.edit(
        "📸 Send a new thumbnail image or tap Skip:",
        reply_markup=thumbnail_kb(prefix),
    )


# ── Cancel ────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^(movie|tv|anime|manhwa)_cancel$"))
async def cb_cancel(client: Client, cb: CallbackQuery):
    await cb.answer("Cancelled.")
    await fsm.clear(cb.from_user.id)
    await cb.message.edit("✅ Cancelled.")
