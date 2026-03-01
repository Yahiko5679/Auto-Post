"""
Template management — /setformat  /myformat  /templates
"""
from pyrofork import Client, filters
from pyrofork.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import CosmicBotz
from utils.fsm import fsm
from utils.helpers import banned_check, track_user


@Client.on_message(filters.command("setformat") & filters.private)
@banned_check
@track_user
async def cmd_setformat(client: Client, message: Message):
    await fsm.set(message.from_user.id, {"step": "tpl_name"})
    await message.reply(
        "📝 **Template Builder**\n\n"
        "**Tokens — All categories:**\n"
        "`{title}` `{year}` `{rating}` `{genres}` `{hashtags}`\n\n"
        "**Movie / TV show:**\n"
        "`{overview}` `{runtime}` `{status}` `{language}`\n"
        "`{imdb_rating}` `{imdb_votes}` `{imdb_url}`\n"
        "`{content_rating}` `{box_office}` `{awards}` `{metacritic}`\n"
        "`{quality}` `{audio}`\n\n"
        "**TV only:** `{seasons}` `{episodes}` `{network}`\n\n"
        "**Anime:** `{synopsis}` `{episodes}` `{type}` `{studio}` `{aired}`\n\n"
        "**Manhwa:** `{synopsis}` `{chapters}` `{type}` `{published}`\n\n"
        "Send a **name** for this template (no spaces, max 32 chars):"
    )


@Client.on_message(filters.command("myformat") & filters.private)
async def cmd_myformat(client: Client, message: Message):
    uid  = message.from_user.id
    s    = await CosmicBotz.get_user_settings(uid)
    name = s.get("active_template", "default")
    if name == "default":
        await message.reply("📋 Using **Default Template**.\nUse /setformat to create a custom one!")
        return
    tpl = await CosmicBotz.get_template(uid, name)
    if not tpl:
        await message.reply("❌ Active template not found in DB.")
        return
    await message.reply(f"📋 **Active: {name}**\n\n`{tpl['body']}`")


@Client.on_message(filters.command("templates") & filters.private)
@banned_check
async def cmd_templates(client: Client, message: Message):
    await show_templates(message.from_user.id, message)


async def show_templates(user_id: int, target):
    templates = await CosmicBotz.list_user_templates(user_id)
    s      = await CosmicBotz.get_user_settings(user_id)
    active = s.get("active_template", "default")

    if not templates:
        text = "📋 **My Templates**\n\nNo custom templates yet.\nUse /setformat to create one!"
        rows = [[InlineKeyboardButton("➕ New Template", callback_data="tpl_new")]]
    else:
        text = f"📋 **My Templates**  (active: `{active}`)\n\n"
        rows = []
        for t in templates:
            mark = "✅" if t["name"] == active else "📄"
            text += f"{mark} `{t['name']}`\n"
            rows.append([
                InlineKeyboardButton(f"👁 View",   callback_data=f"tpl_view|{t['name']}"),
                InlineKeyboardButton("✅ Use",     callback_data=f"tpl_use|{t['name']}"),
                InlineKeyboardButton("🗑 Delete",  callback_data=f"tpl_del|{t['name']}"),
            ])
        rows.append([InlineKeyboardButton("➕ New Template", callback_data="tpl_new")])

    kb = InlineKeyboardMarkup(rows)
    if hasattr(target, "reply"):
        await target.reply(text, reply_markup=kb)
    else:
        await target.edit(text, reply_markup=kb)


@Client.on_callback_query(filters.regex(r"^tpl_"))
async def tpl_callback(client: Client, cb: CallbackQuery):
    await cb.answer()
    uid  = cb.from_user.id
    data = cb.data

    if data == "tpl_new":
        await fsm.set(uid, {"step": "tpl_name"})
        await cb.message.edit("📝 Send a **name** for the new template (no spaces, max 32 chars):")

    elif data.startswith("tpl_view|"):
        name = data.split("|", 1)[1]
        tpl  = await CosmicBotz.get_template(uid, name)
        if tpl:
            await cb.message.edit(
                f"📋 **{name}**\n\n`{tpl['body']}`",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Activate", callback_data=f"tpl_use|{name}"),
                    InlineKeyboardButton("🔙 Back",    callback_data="tpl_back"),
                ]])
            )

    elif data.startswith("tpl_use|"):
        name = data.split("|", 1)[1]
        await CosmicBotz.update_user_settings(uid, {"active_template": name})
        await cb.answer(f"✅ '{name}' activated!", show_alert=True)
        await show_templates(uid, cb.message)

    elif data.startswith("tpl_del|"):
        name = data.split("|", 1)[1]
        await CosmicBotz.delete_template(uid, name)
        s = await CosmicBotz.get_user_settings(uid)
        if s.get("active_template") == name:
            await CosmicBotz.update_user_settings(uid, {"active_template": "default"})
        await cb.answer(f"🗑 Deleted '{name}'", show_alert=True)
        await show_templates(uid, cb.message)

    elif data == "tpl_back":
        await show_templates(uid, cb.message)
