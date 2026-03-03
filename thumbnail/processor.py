"""
Thumbnail Processor — Anime Metrix streaming style
"""

import io
import os
import logging
import aiohttp
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

logger = logging.getLogger(__name__)

_FONT_BOLD = "assets/fonts/DejaVuSans-Bold.ttf"
_FONT_REG  = "assets/fonts/DejaVuSans.ttf"
_SIZE      = (1280, 720)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _fetch(url: str) -> Optional[Image.Image]:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    return Image.open(io.BytesIO(await r.read())).convert("RGBA")
    except Exception as e:
        logger.error(f"Image fetch failed: {e}")
    return None


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    path = _FONT_BOLD if bold else _FONT_REG
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.truetype(_FONT_BOLD, size)
        except Exception:
            return ImageFont.load_default()


def _wrap(text: str, font, draw, max_w: int) -> list:
    words = text.split()
    lines, line = [], []
    for w in words:
        if draw.textlength(" ".join(line + [w]), font=font) > max_w:
            if line:
                lines.append(" ".join(line))
            line = [w]
        else:
            line.append(w)
    if line:
        lines.append(" ".join(line))
    return lines


# ── Watermark — top-left brand logo ──────────────────────────────────────────

def _draw_logo_watermark(canvas: Image.Image, text: str) -> Image.Image:
    """Top-left brand name like 'Anime Metrix' with hamburger menu icon."""
    if not text:
        return canvas

    W, H = canvas.size
    ov   = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od   = ImageDraw.Draw(ov)

    font = _font(26)
    x, y = 72, 18

    # Hamburger menu icon (three lines) to the left of brand name
    hx, hy = 30, 24
    for i in range(3):
        od.rectangle([hx, hy + i * 9, hx + 22, hy + i * 9 + 3], fill=(255, 255, 255, 220))

    # Brand name text
    od.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    return Image.alpha_composite(canvas.convert("RGBA"), ov)


# ── Top-right genre nav bar ───────────────────────────────────────────────────

def _draw_top_nav(canvas: Image.Image, genres: str) -> Image.Image:
    """Render genre tags top-right like a nav bar — Action  Comedy  Adventure."""
    W, H = canvas.size
    ov   = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od   = ImageDraw.Draw(ov)

    items = [g.strip() for g in genres.split(",") if g.strip()][:4] if genres else []
    font  = _font(24, bold=False)

    # Measure total width for right-alignment
    sep     = "    "
    sep_w   = int(od.textlength(sep, font=font))
    widths  = [int(od.textlength(g, font=font)) for g in items]
    total_w = sum(widths) + sep_w * (len(items) - 1) if items else 0

    # Search icon placeholder + close/minimise buttons on far right
    right_margin = 130
    x = W - right_margin - total_w
    y = 22

    for i, g in enumerate(items):
        od.text((x, y), g, font=font, fill=(255, 255, 255, 230))
        x += widths[i]
        if i < len(items) - 1:
            od.text((x, y), sep, font=font, fill=(255, 255, 255, 100))
            x += sep_w

    return Image.alpha_composite(canvas.convert("RGBA"), ov)


# ── Card Builder ──────────────────────────────────────────────────────────────

def _build_card(
    poster: Image.Image,
    backdrop: Optional[Image.Image],
    watermark: str,
    meta: dict,
) -> Image.Image:
    W, H = _SIZE

    # ── Very dark base ────────────────────────────────────────────────────────
    canvas = Image.new("RGBA", (W, H), (12, 14, 20, 255))

    # Full blurred backdrop — very dark (almost black)
    bg = (backdrop or poster).convert("RGBA").resize((W, H), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(10))
    bg = ImageEnhance.Brightness(bg).enhance(0.18)
    canvas.paste(bg.convert("RGBA"), (0, 0))

    # ── Character art — right side, tall, slightly cut at bottom ─────────────
    char_img = poster.convert("RGBA")
    char_h   = int(H * 1.08)
    char_w   = int(char_h * char_img.width / char_img.height)
    char_img = char_img.resize((char_w, char_h), Image.LANCZOS)
    char_x   = W - char_w + int(char_w * 0.05)
    char_y   = -int(H * 0.05)

    # Fade left edge of character art
    fade_w = int(char_w * 0.50)
    for i in range(fade_w):
        alpha = int(255 * (i / fade_w) ** 1.8)
        for yy in range(char_img.height):
            r2, g2, b2, a2 = char_img.getpixel((i, yy))
            char_img.putpixel((i, yy), (r2, g2, b2, min(a2, alpha)))

    # Fade bottom edge
    fade_bot = int(char_h * 0.15)
    for j in range(fade_bot):
        alpha = int(255 * (j / fade_bot))
        yy    = char_h - fade_bot + j
        if yy < char_h:
            for xi in range(char_w):
                r2, g2, b2, a2 = char_img.getpixel((xi, yy))
                char_img.putpixel((xi, yy), (r2, g2, b2, min(a2, alpha)))

    if char_x < W and char_y < H:
        canvas.paste(char_img, (char_x, char_y), char_img)

    # ── Strong left-side dark gradient for text legibility ────────────────────
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(grad)
    for i in range(W):
        alpha = max(0, int(210 - (i / W) * 230))
        gd.line([(i, 0), (i, H)], fill=(8, 10, 16, alpha))
    canvas = Image.alpha_composite(canvas, grad)

    draw = ImageDraw.Draw(canvas)

    # Extract metadata
    title    = meta.get("title", "").upper()
    episodes = str(meta.get("episodes", ""))
    seasons  = str(meta.get("seasons", ""))
    genres   = meta.get("genres", "")
    overview = meta.get("overview") or meta.get("synopsis", "")
    category = meta.get("_category", "")
    runtime  = meta.get("runtime", "")

    left_x = 58
    text_w = int(W * 0.46)

    # ── Title — very large bold white, left aligned ───────────────────────────
    tf     = _font(72)
    tlines = _wrap(title, tf, draw, text_w)[:3]
    title_y = 170
    y       = title_y
    for ln in tlines:
        draw.text((left_x, y), ln, font=tf, fill=(255, 255, 255, 255))
        y += 84
    y += 18

    # ── Description — small grey text ────────────────────────────────────────
    if overview:
        df = _font(23, bold=False)
        for ln in _wrap(overview, df, draw, text_w)[:4]:
            draw.text((left_x, y), ln, font=df, fill=(185, 185, 195, 210))
            y += 31
    y += 28

    # ── Buttons — DOWNLOAD (outline+diagonal cut) + WATCH NOW (red) ──────────
    btn_font = _font(22)
    btn_h    = 50
    btn_gap  = 0   # buttons touch (connected look like reference)

    # DOWNLOAD — dark outline button with right-side diagonal cut
    dl_label = "DOWNLOAD"
    dl_w     = int(draw.textlength(dl_label, font=btn_font)) + 52

    # Draw outline rectangle
    draw.rectangle([left_x, y, left_x + dl_w, y + btn_h], outline=(200, 200, 200, 180), width=2)
    # Diagonal cut on right side (overlap with red button)
    cut_pts = [
        (left_x + dl_w - 14, y),
        (left_x + dl_w + 2,  y),
        (left_x + dl_w + 2,  y + btn_h),
        (left_x + dl_w - 14, y + btn_h),
    ]
    draw.polygon(cut_pts, fill=(12, 14, 20, 255))  # erase corner with bg colour
    dl_tx = left_x + (dl_w - int(draw.textlength(dl_label, font=btn_font))) // 2 - 4
    draw.text((dl_tx, y + 14), dl_label, font=btn_font, fill=(220, 220, 220, 240))

    # WATCH NOW — red filled, starts right after DOWNLOAD
    wn_label = "WATCH NOW"
    wn_x     = left_x + dl_w + btn_gap
    wn_w     = int(draw.textlength(wn_label, font=btn_font)) + 52
    draw.rectangle([wn_x, y, wn_x + wn_w, y + btn_h], fill=(210, 25, 25, 255))
    wn_tx = wn_x + (wn_w - int(draw.textlength(wn_label, font=btn_font))) // 2
    draw.text((wn_tx, y + 14), wn_label, font=btn_font, fill=(255, 255, 255, 255))

    # ── Episode info card — bottom right ─────────────────────────────────────
    card_w, card_h = 360, 128
    card_x = W - card_w - 32
    card_y = H - card_h - 32

    card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    cd   = ImageDraw.Draw(card)
    cd.rounded_rectangle([0, 0, card_w, card_h], radius=10, fill=(18, 20, 28, 230))
    cd.rounded_rectangle([0, 0, card_w, card_h], radius=10, outline=(55, 58, 78, 180), width=1)

    # Thumbnail inside card — right side
    thumb_w, thumb_h = 100, card_h - 16
    thumb_x, thumb_y = card_w - thumb_w - 8, 8
    if backdrop or poster:
        th_img  = (backdrop or poster).convert("RGBA").resize((thumb_w, thumb_h), Image.LANCZOS)
        th_mask = Image.new("L", (thumb_w, thumb_h), 0)
        ImageDraw.Draw(th_mask).rounded_rectangle([0, 0, thumb_w, thumb_h], radius=6, fill=255)
        card.paste(th_img, (thumb_x, thumb_y), th_mask)

    # Episode / Season / Duration text
    ep_str = episodes.zfill(2) if episodes not in ("?", "N/A", "None", "") else "01"
    cd.text((16, 14), f"Episode - {ep_str}", font=_font(28), fill=(255, 255, 255, 255))

    if seasons and seasons not in ("N/A", "None", ""):
        cd.text((16, 52), f"Season - {seasons.zfill(2)}", font=_font(22, bold=False), fill=(190, 190, 200, 220))

    rt_text = runtime if runtime and runtime not in ("N/A", "") else ("23m" if category == "anime" else "")
    if rt_text:
        cd.text((16, 82), f"Duration - {rt_text}", font=_font(22, bold=False), fill=(190, 190, 200, 220))

    canvas.paste(card, (card_x, card_y), card)

    # ── Top nav bar (genre tags right-aligned) ────────────────────────────────
    canvas = _draw_top_nav(canvas, genres)

    # ── Brand watermark top-left ──────────────────────────────────────────────
    canvas = _draw_logo_watermark(canvas, watermark)

    return canvas.convert("RGB")


# ── Public API ────────────────────────────────────────────────────────────────

async def build_thumbnail(
    poster_url: Optional[str],
    backdrop_url: Optional[str] = None,
    watermark: str = "",
    meta: dict = {},
) -> bytes:
    os.makedirs("temp", exist_ok=True)

    poster = (await _fetch(poster_url)) if poster_url else None
    if poster is None:
        poster = Image.new("RGBA", (400, 600), (30, 30, 42, 255))
        ImageDraw.Draw(poster).text((60, 280), "No Image", fill=(120, 120, 140), font=_font(28))

    backdrop = (await _fetch(backdrop_url)) if backdrop_url else None
    card     = _build_card(poster, backdrop, watermark, meta)

    buf = io.BytesIO()
    card.save(buf, format="JPEG", quality=93, optimize=True)
    return buf.getvalue()


async def process_custom_thumbnail(photo_bytes: bytes, watermark: str = "") -> bytes:
    img    = Image.open(io.BytesIO(photo_bytes)).convert("RGBA").resize(_SIZE, Image.LANCZOS)
    canvas = _draw_logo_watermark(img.convert("RGBA"), watermark)

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="JPEG", quality=93, optimize=True)
    return buf.getvalue()