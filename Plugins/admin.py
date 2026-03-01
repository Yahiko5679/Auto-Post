"""
Admin — /admin  /broadcast  /ban  /unban  /addpremium  /revokepremium
        /userinfo  /globalstats
"""
from pyrofork import Client, filters
from pyrofork.types import Message, CallbackQuery

from database.db import CosmicBotz
from utils.fsm import fsm
from utils.helpers import admin_only, admin_kb
import config as cfg


# ── Commands ──────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("admin") & filters.private)
@admin_only
async def cmd_admin(client: Client, message: Message):
    tu = await CosmicBotz.total_users()
    tp = await CosmicBotz.total_posts()
    await message.reply(
        f"👑 **Admin Panel**\n\n"
        f"👥 Total Users: **{tu}**\n"
        f"📤 Total Posts: **{tp}**",
        reply_markup=admin_kb(),
    )


@Client.on_message(filters.command("broadcast") & filters.private)
@admin_only
async def cmd_broadcast(client: Client, message: Message):
    await fsm.set(message.from_user.id, {"step": "adm_broadcast"})
    await message.reply("📢 Send the message to broadcast to all users:")


@Client.on_message(filters.command("ban") & filters.private)
@admin_only
async def cmd_ban(client: Client, message: Message):
    args = message.command[1:]
    if not args:
        await message.reply("Usage: `/ban <user_id>`")
        return
    uid = int(args[0])
    await CosmicBotz.ban_user(uid)
    await message.reply(f"⛔ User `{uid}` banned.")


@Client.on_message(filters.command("unban") & filters.private)
@admin_only
async def cmd_unban(client: Client, message: Message):
    args = message.command[1:]
    if not args:
        await message.reply("Usage: `/unban <user_id>`")
        return
    uid = int(args[0])
    await CosmicBotz.unban_user(uid)
    await message.reply(f"✅ User `{uid}` unbanned.")


@Client.on_message(filters.command("addpremium") & filters.private)
@admin_only
async def cmd_addpremium(client: Client, message: Message):
    args = message.command[1:]
    if not args:
        await message.reply("Usage: `/addpremium <user_id>`")
        return
    uid = int(args[0])
    await CosmicBotz.set_premium(uid, True)
    await message.reply(f"⭐ User `{uid}` upgraded to Premium.")
    try:
        await client.send_message(
            uid,
            "🎉 **You've been upgraded to ⭐ Premium!**\n"
            "Enjoy unlimited posts and all features!"
        )
    except Exception:
        pass


@Client.on_message(filters.command("revokepremium") & filters.private)
@admin_only
async def cmd_revokepremium(client: Client, message: Message):
    args = message.command[1:]
    if not args:
        await message.reply("Usage: `/revokepremium <user_id>`")
        return
    uid = int(args[0])
    await CosmicBotz.set_premium(uid, False)
    await message.reply(f"✅ Premium revoked for `{uid}`.")


@Client.on_message(filters.command("userinfo") & filters.private)
@admin_only
async def cmd_userinfo(client: Client, message: Message):
    args = message.command[1:]
    if not args:
        await message.reply("Usage: `/userinfo <user_id>`")
        return
    uid  = int(args[0])
    user = await CosmicBotz.get_user(uid)
    if not user:
        await message.reply("❌ User not found.")
        return
    await message.reply(
        f"👤 **User Info**\n\n"
        f"ID:       `{uid}`\n"
        f"Name:     {user.get('full_name', 'N/A')}\n"
        f"Username: @{user.get('username', 'N/A')}\n"
        f"Posts:    **{user.get('post_count', 0)}**\n"
        f"Premium:  {'⭐ Yes' if user.get('is_premium') else 'No'}\n"
        f"Banned:   {'⛔ Yes' if user.get('is_banned') else 'No'}\n"
        f"Joined:   {str(user.get('joined', 'N/A'))[:10]}"
    )


@Client.on_message(filters.command("globalstats") & filters.private)
@admin_only
async def cmd_globalstats(client: Client, message: Message):
    tu = await CosmicBotz.total_users()
    tp = await CosmicBotz.total_posts()
    await message.reply(
        f"📊 **Global Stats**\n\n"
        f"👥 Total Users: **{tu}**\n"
        f"📤 Total Posts: **{tp}**"
    )


# ── Broadcast ─────────────────────────────────────────────────────────────────

async def do_broadcast(client: Client, message: Message, text: str):
    await fsm.clear(message.from_user.id)
    user_ids = await CosmicBotz.get_all_user_ids()
    status   = await message.reply(f"📤 Broadcasting to **{len(user_ids)}** users...")
    ok = fail = 0
    for uid in user_ids:
        try:
            await client.send_message(uid, f"📢 **Announcement**\n\n{text}")
            ok += 1
        except Exception:
            fail += 1
    await status.edit(f"✅ Done!  ✔ Sent: **{ok}**  ✘ Failed: **{fail}**")


# ── Admin callbacks ───────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^adm_"))
async def adm_callback(client: Client, cb: CallbackQuery):
    if cb.from_user.id not in cfg.ADMIN_IDS:
        await cb.answer("⛔ Admin only.", show_alert=True)
        return
    await cb.answer()
    data = cb.data

    if data == "adm_stats":
        tu = await CosmicBotz.total_users()
        tp = await CosmicBotz.total_posts()
        await cb.message.edit(
            f"📊 **Stats**\n\nUsers: **{tu}**\nPosts: **{tp}**",
            reply_markup=admin_kb(),
        )
    elif data == "adm_broadcast":
        await fsm.set(cb.from_user.id, {"step": "adm_broadcast"})
        await cb.message.edit("📢 Send the broadcast message:")
    elif data == "adm_close":
        await cb.message.delete()
