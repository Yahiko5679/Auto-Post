"""
/start  /help  /stats
"""
from pyrofork import Client, filters
from pyrofork.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from database.db import CosmicBotz
from utils.helpers import track_user, banned_check
import config as cfg


@Client.on_message(filters.command("start") & filters.private)
@banned_check
@track_user
async def cmd_start(client: Client, message: Message):
    name = message.from_user.first_name
    await message.reply(
        f"👋 **Hello, {name}!**\n\n"
        "🤖 **CosmicBotz — AutoPost Generator**\n\n"
        "Generate beautiful posts for your Telegram channels in seconds!\n\n"
        "**📌 Quick Start:**\n"
        "┌ /movie `Inception`\n"
        "├ /tvshow `Breaking Bad`\n"
        "├ /anime `Attack on Titan`\n"
        "└ /manhwa `Solo Leveling`\n\n"
        "⚙️ /settings  📋 /templates  ❓ /help",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎬 Movie",   callback_data="eg_movie"),
                InlineKeyboardButton("📺 TV Show", callback_data="eg_tv"),
            ],
            [
                InlineKeyboardButton("🌸 Anime",   callback_data="eg_anime"),
                InlineKeyboardButton("📖 Manhwa",  callback_data="eg_manhwa"),
            ],
            [InlineKeyboardButton("⚙️ Settings",  callback_data="cfg_open")],
        ]),
    )


@Client.on_message(filters.command("help") & filters.private)
async def cmd_help(client: Client, message: Message):
    await message.reply(
        "📖 **CosmicBotz — Help**\n\n"
        "**Content:**\n"
        "/movie `<title>` — Movie post\n"
        "/tvshow `<title>` — TV show post\n"
        "/anime `<title>` — Anime post\n"
        "/manhwa `<title>` — Manhwa post\n\n"
        "**Customise:**\n"
        "/settings — Full settings panel\n"
        "/setwatermark — Set thumbnail watermark\n"
        "/setchannel — Link your channel\n"
        "/setformat — Create caption template\n"
        "/templates — Manage templates\n"
        "/myformat — View active template\n\n"
        "**Info:**\n"
        "/stats — Your usage stats\n\n"
        "**How it works:**\n"
        "`1.` Type command + title\n"
        "`2.` Pick from search results\n"
        "`3.` Upload custom thumbnail or skip\n"
        "`4.` Preview your post\n"
        "`5.` Post to channel or copy caption!"
    )


@Client.on_message(filters.command("stats") & filters.private)
async def cmd_stats(client: Client, message: Message):
    user = await CosmicBotz.get_user(message.from_user.id)
    if not user:
        await message.reply("No stats yet — generate your first post!")
        return
    plan = "⭐ Premium" if user.get("is_premium") else "Free"
    await message.reply(
        f"📊 **Your Stats**\n\n"
        f"Total Posts: **{user.get('post_count', 0)}**\n"
        f"Account:     **{plan}**"
    )


@Client.on_callback_query(filters.regex(r"^eg_"))
async def cb_example(client: Client, cb: CallbackQuery):
    tips = {
        "eg_movie":  "Try: `/movie Interstellar`",
        "eg_tv":     "Try: `/tvshow Game of Thrones`",
        "eg_anime":  "Try: `/anime Demon Slayer`",
        "eg_manhwa": "Try: `/manhwa Tower of God`",
    }
    await cb.answer(tips.get(cb.data, ""), show_alert=True)
