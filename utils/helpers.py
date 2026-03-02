#from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import config as cfg


def extract_query(text: str) -> str:
    """Extract search query from command text."""
    parts = text.split(None, 1)
    return parts[1].strip() if len(parts) > 1 else ""


def search_kb(results: list, prefix: str):
    kb = InlineKeyboardBuilder()
    for r in results[:cfg.MAX_SEARCH_RESULTS]:
        label = f"{r.get('title', 'Unknown')} ({r.get('year', '?')})"
        kb.button(text=label[:64], callback_data=f"{prefix}_select_{r['id']}")
    kb.button(text="❌ Cancel", callback_data=f"{prefix}_cancel")
    kb.adjust(1)
    return kb.as_markup()


def thumbnail_kb(prefix: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Skip — Use Auto Poster", callback_data=f"{prefix}_thumb_skip")
    kb.button(text="❌ Cancel",                 callback_data=f"{prefix}_cancel")
    kb.adjust(1)
    return kb.as_markup()


def preview_kb(prefix: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Post to Channel",   callback_data=f"{prefix}_post_channel")
    kb.button(text="📋 Copy Caption",      callback_data=f"{prefix}_post_copy")
    kb.button(text="🖼 Change Thumbnail",  callback_data=f"{prefix}_redo_thumb")
    kb.button(text="📄 Change Template",   callback_data=f"{prefix}_change_tpl")
    kb.button(text="❌ Cancel",             callback_data=f"{prefix}_cancel")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def template_kb(templates: list, prefix: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="⬜ Default", callback_data=f"{prefix}_tpl_default")
    for t in templates:
        kb.button(text=f"📄 {t['name']}", callback_data=f"{prefix}_tpl_{t['name']}")
    kb.button(text="🔙 Back", callback_data=f"{prefix}_back_preview")
    kb.adjust(1)
    return kb.as_markup()


async def post_to_channel(bot, channel_id: str, thumb: bytes, caption: str) -> bool:
    from aiogram.types import BufferedInputFile
    try:
        photo = BufferedInputFile(thumb, filename="thumb.jpg")
        await bot.send_photo(chat_id=channel_id, photo=photo, caption=caption)
        return True
    except Exception:
        return False


# ── New button-related keyboards ───────────────────────────────────────

def ask_add_buttons_kb(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Add button(s)", callback_data=f"{prefix}_add_buttons")
    builder.button(text="Skip → Post",   callback_data=f"{prefix}_post_no_buttons")
    builder.adjust(2)
    return builder.as_markup()


def finish_adding_kb(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Finish & Preview", callback_data=f"{prefix}_finish_buttons")
    builder.button(text="Cancel",           callback_data=f"{prefix}_cancel")
    builder.adjust(2)
    return builder.as_markup()


def confirm_post_with_buttons_kb(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Post Now",      callback_data=f"{prefix}_confirm_post_buttons")
    builder.button(text="✏️ Edit / Add more", callback_data=f"{prefix}_add_buttons")
    builder.button(text="❌ Cancel",         callback_data=f"{prefix}_cancel")
    builder.adjust(1, 2)
    return builder.as_markup()