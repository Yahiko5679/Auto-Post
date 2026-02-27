"""
Admin Handler — broadcast, ban, premium management, stats.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db import CosmicBotz
from fsm.state_manager import StateManager
from utils.keyboards import admin_kb
from utils.helpers import safe_edit, safe_answer, require_admin, track_user
from config import ADMIN_IDS

logger = logging.getLogger(__name__)


class AdminHandler:
    def __init__(self):
        self.sm = StateManager()

    @require_admin
    async def panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        tu = await CosmicBotz.total_users()
        tp = await CosmicBotz.total_posts()
        await update.message.reply_text(
            f"👑 <b>Admin Panel</b>\n\n"
            f"👥 Total Users: <b>{tu}</b>\n"
            f"📤 Total Posts: <b>{tp}</b>\n",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_kb(),
        )

    @require_admin
    async def broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        await self.sm.set_state(user_id, {"awaiting_broadcast": True})
        await update.message.reply_text(
            "📢 <b>Broadcast</b>\n\nSend the message to broadcast to all users:",
            parse_mode=ParseMode.HTML,
        )

    async def handle_broadcast_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        await self.sm.clear_state(user_id)

        user_ids = await CosmicBotz.get_all_user_ids()
        success, fail = 0, 0

        status_msg = await update.message.reply_text(
            f"📤 Broadcasting to {len(user_ids)} users..."
        )

        for uid in user_ids:
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"📢 <b>Announcement</b>\n\n{text}",
                    parse_mode=ParseMode.HTML,
                )
                success += 1
            except Exception:
                fail += 1

        await status_msg.edit_text(
            f"✅ Broadcast complete!\n✔ Sent: {success}\n✘ Failed: {fail}"
        )

    @require_admin
    async def ban_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /ban <user_id>")
            return
        uid = int(args[0])
        await CosmicBotz.ban_user(uid)
        await update.message.reply_text(f"⛔ User {uid} banned.")

    @require_admin
    async def unban_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /unban <user_id>")
            return
        uid = int(args[0])
        await CosmicBotz.unban_user(uid)
        await update.message.reply_text(f"✅ User {uid} unbanned.")

    @require_admin
    async def add_premium(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /addpremium <user_id>")
            return
        uid = int(args[0])
        await CosmicBotz.set_premium(uid, True)
        await update.message.reply_text(f"⭐ User {uid} is now Premium.")
        try:
            await context.bot.send_message(
                uid,
                "🎉 <b>Congratulations!</b> You've been upgraded to ⭐ <b>Premium</b>!\n"
                "Enjoy unlimited posts and all features!",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    @require_admin
    async def revoke_premium(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /revokepremium <user_id>")
            return
        uid = int(args[0])
        await CosmicBotz.set_premium(uid, False)
        await update.message.reply_text(f"Premium revoked for user {uid}.")

    @require_admin
    async def user_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /userinfo <user_id>")
            return
        uid = int(args[0])
        user = await CosmicBotz.get_user(uid)
        if not user:
            await update.message.reply_text("❌ User not found.")
            return
        await update.message.reply_text(
            f"👤 <b>User Info</b>\n\n"
            f"ID: <code>{uid}</code>\n"
            f"Name: {user.get('full_name', 'N/A')}\n"
            f"Username: @{user.get('username', 'N/A')}\n"
            f"Posts: {user.get('post_count', 0)}\n"
            f"Premium: {'⭐ Yes' if user.get('is_premium') else 'No'}\n"
            f"Banned: {'⛔ Yes' if user.get('is_banned') else 'No'}\n"
            f"Joined: {user.get('joined', 'N/A')}\n",
            parse_mode=ParseMode.HTML,
        )

    @require_admin
    async def global_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        tu = await CosmicBotz.total_users()
        tp = await CosmicBotz.total_posts()
        await update.message.reply_text(
            f"📊 <b>Global Stats</b>\n\n"
            f"👥 Total Users: <b>{tu}</b>\n"
            f"📤 Total Posts Generated: <b>{tp}</b>",
            parse_mode=ParseMode.HTML,
        )

    async def callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await safe_answer(query)
        data = query.data

        if data == "admin_stats":
            tu = await CosmicBotz.total_users()
            tp = await CosmicBotz.total_posts()
            await safe_edit(
                query.message,
                f"📊 <b>Global Stats</b>\n\n"
                f"👥 Total Users: <b>{tu}</b>\n"
                f"📤 Total Posts: <b>{tp}</b>",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="admin_back")
                ]])
            )

        elif data == "admin_broadcast":
            user_id = update.effective_user.id
            await self.sm.set_state(user_id, {"awaiting_broadcast": True})
            await safe_edit(
                query.message,
                "📢 Send the message to broadcast:"
            )

        elif data == "admin_back":
            tu = await CosmicBotz.total_users()
            tp = await CosmicBotz.total_posts()
            await safe_edit(
                query.message,
                f"👑 <b>Admin Panel</b>\n\n"
                f"👥 Users: {tu} | 📤 Posts: {tp}",
                reply_markup=admin_kb(),
            )

        elif data == "admin_close":
            await query.message.delete()
