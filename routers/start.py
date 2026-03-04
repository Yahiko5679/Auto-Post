from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import CosmicBotz
from routers.admin import check_mode, is_admin

router = Router()


async def _ensure_user(message: Message):
    await CosmicBotz.upsert_user(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.full_name or "",
    )


@router.message(Command("start"))
async def cmd_start(message: Message):
    await _ensure_user(message)

    # Ban check first
    if await CosmicBotz.is_banned(message.from_user.id):
        await message.answer("⛔ You are banned from using this bot.")
        return

    # Mode check — /start always shows, but we append a notice if restricted
    allowed, reason = await check_mode(message.from_user.id)

    name = message.from_user.first_name or "there"
    kb   = InlineKeyboardBuilder()
    kb.button(text="🎬 Movie",    callback_data="eg_movie")
    kb.button(text="📺 TV Show",  callback_data="eg_tv")
    kb.button(text="🌸 Anime",    callback_data="eg_anime")
    kb.button(text="📖 Manhwa",   callback_data="eg_manhwa")
    kb.button(text="⚙️ Settings", callback_data="cfg_open")
    kb.adjust(2, 2, 1)

    if not allowed:
        # Show restricted message instead of full panel
        await message.answer(
            f"👋 <b>Hello, {name}!</b>\n\n{reason}",
            reply_markup=None,
        )
        return

    await message.answer(
        f"👋 <b>Hello, {name}!</b>\n\n"
        "🤖 <b>CosmicBotz — AutoPost Generator</b>\n\n"
        "Generate beautiful posts for your Telegram channels!\n\n"
        "<b>📌 Quick Start:</b>\n"
        "┌ /movie <code>Inception</code>\n"
        "├ /tvshow <code>Breaking Bad</code>\n"
        "├ /anime <code>Attack on Titan</code>\n"
        "└ /manhwa <code>Solo Leveling</code>\n\n"
        "⚙️ /settings  📋 /templates  ❓ /help",
        reply_markup=kb.as_markup(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await _ensure_user(message)

    if await CosmicBotz.is_banned(message.from_user.id):
        await message.answer("⛔ You are banned from using this bot.")
        return

    allowed, reason = await check_mode(message.from_user.id)
    if not allowed:
        await message.answer(reason)
        return

    await message.answer(
        "📖 <b>CosmicBotz — Help</b>\n\n"
        "<b>Content:</b>\n"
        "/movie <code>title</code> — Movie post\n"
        "/tvshow <code>title</code> — TV show post\n"
        "/anime <code>title</code> — Anime post\n"
        "/manhwa <code>title</code> — Manhwa post\n\n"
        "<b>Customise:</b>\n"
        "/settings — Full settings panel\n"
        "/setwatermark — Set thumbnail watermark\n"
        "/setchannel — Link your channel\n"
        "/templates — Manage templates\n"
        "/buttonsets — Manage button sets\n\n"
        "<b>Info:</b>\n"
        "/stats — Your usage stats"
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    await _ensure_user(message)

    if await CosmicBotz.is_banned(message.from_user.id):
        await message.answer("⛔ You are banned from using this bot.")
        return

    user  = await CosmicBotz.get_user(message.from_user.id)
    plan  = "⭐ Premium" if user and user.get("is_premium") else "Free"
    posts = user.get("post_count", 0) if user else 0
    today = str(__import__("datetime").date.today())
    today_posts = user.get("daily_posts", {}).get(today, 0) if user else 0
    await message.answer(
        f"📊 <b>Your Stats</b>\n\n"
        f"Total Posts: <b>{posts}</b>\n"
        f"Today:       <b>{today_posts}</b>\n"
        f"Account:     <b>{plan}</b>"
    )


@router.callback_query(F.data.startswith("eg_"))
async def cb_example(cb: CallbackQuery):
    tips = {
        "eg_movie":  "Try: /movie Interstellar",
        "eg_tv":     "Try: /tvshow Game of Thrones",
        "eg_anime":  "Try: /anime Demon Slayer",
        "eg_manhwa": "Try: /manhwa Tower of God",
    }
    await cb.answer(tips.get(cb.data, ""), show_alert=True)