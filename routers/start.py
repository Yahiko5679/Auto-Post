from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import CosmicBotz

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    await CosmicBotz.upsert_user(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.full_name or "",
    )
    name = message.from_user.first_name
    kb = InlineKeyboardBuilder()
    kb.button(text="🎬 Movie",   callback_data="eg_movie")
    kb.button(text="📺 TV Show", callback_data="eg_tv")
    kb.button(text="🌸 Anime",   callback_data="eg_anime")
    kb.button(text="📖 Manhwa",  callback_data="eg_manhwa")
    kb.button(text="⚙️ Settings", callback_data="cfg_open")
    kb.adjust(2, 2, 1)
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
        "/setformat — Create caption template\n"
        "/templates — Manage templates\n\n"
        "<b>Info:</b>\n"
        "/stats — Your usage stats"
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    user = await CosmicBotz.get_user(message.from_user.id)
    if not user:
        await message.answer("No stats yet — generate your first post!")
        return
    plan = "⭐ Premium" if user.get("is_premium") else "Free"
    await message.answer(
        f"📊 <b>Your Stats</b>\n\n"
        f"Total Posts: <b>{user.get('post_count', 0)}</b>\n"
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
