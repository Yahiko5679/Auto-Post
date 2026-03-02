"""
Thumbnail Processor
Builds 1280x720 JPEG cards from poster + backdrop images.
"""
import io
import os
import logging
import aiohttp
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

logger = logging.getLogger(__name__)

_FONT_PATH = "assets/fonts/DejaVuSans-Bold.ttf"
_SIZE      = (1280, 720)


async def _fetch(url: str) -> Optional[Image.Image]:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    return Image.open(io.BytesIO(await r.read())).convert("RGBA")
    except Exception as e:
        logger.error(f"Image fetch failed: {e}")
    return None


def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(_FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


def _watermark(img: Image.Image, text: str) -> Image.Image:
    if not text:
        return img
    draw = ImageDraw.Draw(img)
    font = _font(26)
    W, H = img.size
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    m = 14
    # ✅ TOP-RIGHT (changed from bottom-right)
    x = W - tw - m * 2 - 10
    y = 10
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.rounded_rectangle([x, y, x + tw + m*2, y + th + m*2], radius=8, fill=(0, 0, 0, 160))
    od.text((x + m, y + m), text, font=font, fill=(255, 255, 255, 230))
    return Image.alpha_composite(img, ov)


def _draw_text_block(draw: ImageDraw.Draw, meta: dict, rx: int, ry: int, rw: int):
    """Draw title, genres, rating info on the right panel."""
    title    = meta.get("title", "")
    year     = meta.get("year", "")
    genres   = meta.get("genres", "")
    rating   = meta.get("imdb_rating") or meta.get("rating", "")
    status   = meta.get("status", "")
    episodes = meta.get("episodes", "")
    seasons  = meta.get("seasons", "")
    category = meta.get("_category", "")

    y = ry

    # Title — wrap long titles
    title_font = _font(38)
    words = title.split()
    lines, line = [], []
    for w in words:
        test = " ".join(line + [w])
        if draw.textlength(test, font=title_font) > rw - 20:
            if line:
                lines.append(" ".join(line))
            line = [w]
        else:
            line.append(w)
    if line:
        lines.append(" ".join(line))

    for ln in lines[:2]:
        draw.text((rx, y), ln, font=title_font, fill=(255, 255, 255, 255))
        y += 46

    y += 8

    # Year pill
    if year:
        draw.text((rx, y), f"📅 {year}", font=_font(24), fill=(200, 200, 200, 220))
        y += 34

    # Rating
    if rating and str(rating) not in ("N/A", "0", ""):
        draw.text((rx, y), f"⭐ {rating}", font=_font(24), fill=(255, 210, 60, 240))
        y += 34

    # Status
    if status and status != "N/A":
        draw.text((rx, y), f"📡 {status}", font=_font(22), fill=(150, 220, 150, 220))
        y += 32

    # Episodes / Seasons
    if episodes and str(episodes) not in ("N/A", "?", ""):
        draw.text((rx, y), f"🎬 Episodes: {episodes}", font=_font(22), fill=(200, 200, 200, 200))
        y += 30
    if seasons and str(seasons) not in ("N/A", ""):
        draw.text((rx, y), f"📺 Seasons: {seasons}", font=_font(22), fill=(200, 200, 200, 200))
        y += 30

    y += 10

    # Genres — split and draw as pills
    if genres:
        glist = [g.strip() for g in genres.split(",") if g.strip()][:4]
        gx = rx
        for g in glist:
            gw = int(draw.textlength(g, font=_font(19))) + 20
            if gx + gw > rx + rw:
                break
            # pill background
            pill_img = Image.new("RGBA", (gw, 28), (0, 0, 0, 0))
            pill_draw = ImageDraw.Draw(pill_img)
            pill_draw.rounded_rectangle([0, 0, gw, 28], radius=8, fill=(255, 200, 50, 60))
            pill_draw.text((10, 4), g, font=_font(19), fill=(255, 220, 100, 220))
            draw._image.paste(pill_img, (gx, y), pill_img)
            gx += gw + 8


def _build_card(poster: Image.Image, backdrop: Optional[Image.Image], watermark: str, meta: dict = {}) -> Image.Image:
    W, H = _SIZE
    canvas = Image.new("RGBA", (W, H), (15, 15, 20, 255))

    # Background: blurred backdrop or poster
    bg = (backdrop or poster).convert("RGBA").resize((W, H), Image.LANCZOS)
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(18))).enhance(0.35)
    canvas.paste(bg, (0, 0))

    # Dark gradient left→right so right panel is readable
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(grad)
    for i in range(W):
        alpha = int(60 + (i / W) * 160)
        gd.line([(i, 0), (i, H)], fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas, grad)

    # Poster dimensions
    ph = int(H * 0.82)
    pw = int(ph * 2 / 3)
    px, py = 50, (H - ph) // 2

    # Shadow behind poster
    sb = Image.new("RGBA", (pw + 20, ph + 20), (0, 0, 0, 180))
    sb_blur = sb.filter(ImageFilter.GaussianBlur(12))
    canvas.paste(sb_blur, (px - 5, py + 8), sb_blur)

    # Rounded poster
    pr   = poster.convert("RGBA").resize((pw, ph), Image.LANCZOS)
    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw, ph], radius=14, fill=255)
    canvas.paste(pr, (px, py), mask)

    # Accent line between poster and info
    ax = px + pw + 22
    ImageDraw.Draw(canvas).line([(ax, py + 10), (ax, py + ph - 10)], fill=(255, 200, 50, 200), width=3)

    # Right panel — draw info text
    rx  = ax + 22
    ry  = py + 20
    rw  = W - rx - 30
    draw = ImageDraw.Draw(canvas)
    _draw_text_block(draw, meta, rx, ry, rw)

    return _watermark(canvas, watermark).convert("RGB")


async def build_thumbnail(
    poster_url: Optional[str],
    backdrop_url: Optional[str] = None,
    watermark: str = "",
    meta: dict = {},
) -> bytes:
    """Download images and build a 1280x720 card. Returns JPEG bytes."""
    os.makedirs("temp", exist_ok=True)

    poster = (await _fetch(poster_url)) if poster_url else None
    if poster is None:
        poster = Image.new("RGBA", (400, 600), (30, 30, 40, 255))
        ImageDraw.Draw(poster).text((20, 280), "No Image", fill=(200, 200, 200), font=_font(24))

    backdrop = (await _fetch(backdrop_url)) if backdrop_url else None
    card = _build_card(poster, backdrop, watermark, meta)

    buf = io.BytesIO()
    card.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()


async def process_custom_thumbnail(photo_bytes: bytes, watermark: str = "") -> bytes:
    """Resize user-uploaded photo to 1280x720 and apply watermark."""
    img = Image.open(io.BytesIO(photo_bytes)).convert("RGBA").resize(_SIZE, Image.LANCZOS)
    img = _watermark(img, watermark).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()