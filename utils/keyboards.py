"""
Keyboard / InlineKeyboard Builder helpers
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Optional


def search_results_kb(results: List[Dict], category: str) -> InlineKeyboardMarkup:
    """Result selection keyboard from search list."""
    prefix = {"movie": "movie", "tvshow": "tv", "anime": "anime", "manhwa": "manhwa"}[category]
    rows = []
    for r in results:
        label = f"{r['title']} ({r.get('year', '?')})"
        rows.append([InlineKeyboardButton(label, callback_data=f"{prefix}_select_{r['id']}")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data=f"{prefix}_cancel")])
    return InlineKeyboardMarkup(rows)


def thumbnail_kb(category: str) -> InlineKeyboardMarkup:
    prefix = category_prefix(category)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Skip → Use Auto Poster", callback_data=f"{prefix}_thumb_skip")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"{prefix}_cancel")],
    ])


def post_preview_kb(category: str) -> InlineKeyboardMarkup:
    prefix = category_prefix(category)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Post to Channel", callback_data=f"{prefix}_post_channel"),
            InlineKeyboardButton("📋 Copy Caption",   callback_data=f"{prefix}_post_copy"),
        ],
        [
            InlineKeyboardButton("🔄 Change Template", callback_data=f"{prefix}_change_template"),
            InlineKeyboardButton("🖼 Re-do Thumbnail",  callback_data=f"{prefix}_redo_thumb"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"{prefix}_cancel")],
    ])


def template_select_kb(templates: List[Dict], category: str) -> InlineKeyboardMarkup:
    prefix = category_prefix(category)
    rows = []
    rows.append([InlineKeyboardButton("⭐ Default Template", callback_data=f"{prefix}_tpl_default")])
    for t in templates:
        rows.append([InlineKeyboardButton(
            f"📄 {t['name']}", callback_data=f"{prefix}_tpl_{t['name']}"
        )])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data=f"{prefix}_back_preview")])
    return InlineKeyboardMarkup(rows)


def settings_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖋 Set Watermark",   callback_data="settings_watermark"),
            InlineKeyboardButton("📺 Set Channel",     callback_data="settings_channel"),
        ],
        [
            InlineKeyboardButton("🎞 Set Quality",     callback_data="settings_quality"),
            InlineKeyboardButton("🔊 Set Audio",       callback_data="settings_audio"),
        ],
        [
            InlineKeyboardButton("📋 My Templates",    callback_data="settings_templates"),
            InlineKeyboardButton("📊 My Stats",        callback_data="settings_stats"),
        ],
        [InlineKeyboardButton("❌ Close", callback_data="settings_close")],
    ])


def quality_kb() -> InlineKeyboardMarkup:
    options = [
        "480p | 720p | 1080p",
        "720p | 1080p | 4K",
        "480p | 720p",
        "1080p | 4K",
        "480p Only",
    ]
    rows = [[InlineKeyboardButton(o, callback_data=f"settings_setquality_{o}")] for o in options]
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="settings_back")])
    return InlineKeyboardMarkup(rows)


def audio_kb() -> InlineKeyboardMarkup:
    options = [
        "Hindi | English",
        "Hindi | English | Tamil | Telugu",
        "English Only",
        "Multi Audio",
        "Dual Audio",
    ]
    rows = [[InlineKeyboardButton(o, callback_data=f"settings_setaudio_{o}")] for o in options]
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="settings_back")])
    return InlineKeyboardMarkup(rows)


def admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Global Stats",    callback_data="admin_stats"),
            InlineKeyboardButton("📢 Broadcast",       callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton("👑 Add Premium",     callback_data="admin_addpremium"),
            InlineKeyboardButton("⛔ Ban User",        callback_data="admin_ban"),
        ],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
    ])


def confirm_kb(yes_data: str, no_data: str, yes_label="✅ Yes", no_label="❌ No") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(yes_label, callback_data=yes_data),
            InlineKeyboardButton(no_label,  callback_data=no_data),
        ]
    ])


def category_prefix(category: str) -> str:
    return {"movie": "movie", "tvshow": "tv", "anime": "anime", "manhwa": "manhwa"}[category]
