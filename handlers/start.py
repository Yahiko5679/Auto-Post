"""
Start / Help / Stats Handler
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db import CosmicBotz
from utils.helpers import track_user


class StartHandler:
    @track_user
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        text = (
            f"👋 Hello, <b>{user.first_name}</b>!\n\n"
            f"🤖 <b>AutoPost Generator Bot</b>\n\n"
            f"I help you generate beautiful, ready-to-post content for your Telegram channels.\n\n"
            f"<b>📌 Quick Start:</b>\n"
            f"┌ /movie Inception\n"
            f"├ /tvshow Breaking Bad\n"
            f"├ /anime Attack on Titan\n"
            f"└ /manhwa Solo Leveling\n\n"
            f"<b>⚙️ Customize:</b>\n"
            f"┌ /settings — watermark, channel, quality\n"
            f"├ /setformat — build custom post templates\n"
            f"└ /templates — manage your templates\n\n"
            f"Type /help for full command list."
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎬 Movie",   callback_data="start_example_movie"),
                InlineKeyboardButton("📺 TV Show", callback_data="start_example_tv"),
            ],
            [
                InlineKeyboardButton("🌸 Anime",   callback_data="start_example_anime"),
                InlineKeyboardButton("📖 Manhwa",  callback_data="start_example_manhwa"),
            ],
            [InlineKeyboardButton("⚙️ Settings",  callback_data="start_settings")],
        ])
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "📖 <b>Command Reference</b>\n\n"
            "<b>Content Generation:</b>\n"
            "/movie &lt;title&gt; — Generate movie post\n"
            "/tvshow &lt;title&gt; — Generate TV show post\n"
            "/anime &lt;title&gt; — Generate anime post\n"
            "/manhwa &lt;title&gt; — Generate manhwa post\n\n"
            "<b>Customization:</b>\n"
            "/settings — Open settings panel\n"
            "/setformat — Create a custom format template\n"
            "/templates — View & manage your templates\n"
            "/myformat — Show your active template\n"
            "/setwatermark — Set thumbnail watermark\n"
            "/setchannel — Link your Telegram channel\n\n"
            "<b>Info:</b>\n"
            "/stats — Your usage stats\n"
            "/help — This message\n\n"
            "<b>💡 How it works:</b>\n"
            "1. Type a command with a title\n"
            "2. Select from search results\n"
            "3. Send a custom thumbnail or skip\n"
            "4. Preview your post\n"
            "5. Post to channel or copy caption!"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = await CosmicBotz.get_user(update.effective_user.id)
        if not user:
            await update.message.reply_text("No stats yet. Start generating posts!")
            return
        posts = user.get("post_count", 0)
        premium = "⭐ Premium" if user.get("is_premium") else "Free"
        await update.message.reply_text(
            f"📊 <b>Your Stats</b>\n\n"
            f"Total Posts Generated: <b>{posts}</b>\n"
            f"Account Type: <b>{premium}</b>",
            parse_mode=ParseMode.HTML,
        )

    async def callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from utils.helpers import safe_answer
        query = update.callback_query
        await safe_answer(query)
        data = query.data

        examples = {
            "start_example_movie":   "Try: /movie Interstellar",
            "start_example_tv":      "Try: /tvshow Game of Thrones",
            "start_example_anime":   "Try: /anime Demon Slayer",
            "start_example_manhwa":  "Try: /manhwa Tower of God",
        }
        if data in examples:
            await query.answer(examples[data], show_alert=True)
        elif data == "start_settings":
            from handlers.settings import SettingsHandler
            await SettingsHandler().menu(update, context)
