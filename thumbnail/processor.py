"""
Thumbnail Processor — Streaming platform dark style (Anime Metrix reference)
Updated: better right-side image visibility & premium button UX
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


def _draw_logo_watermark(canvas: Image.Image, text: str) -> Image.Image:
    if not text:
        return canvas
    W, H  = canvas.size
    font  = _font(28)
    ov    = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od    = ImageDraw.Draw(ov)
    bbox  = od.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = 18, 10
    x = W - tw - px * 2 - 12
    y = 14
    od.rectangle([x, y, x + 4, y + th + py * 2], fill=(220, 30, 30, 240))
    od.rectangle([x + 4, y, x + tw + px * 2 + 4, y + th + py * 2], fill=(10, 10, 10, 200))
    od.text((x + px + 4, y + py), text, font=font, fill=(255, 255, 255, 255))
    return Image.alpha_composite(canvas.convert("RGBA"), ov)


def _draw_genre_tags(draw: ImageDraw.Draw, genres: str, gx: int, gy: int, max_w: int):
    if not genres:
        return
    items = [g.strip() for g in genres.split(",") if g.strip()][:5]
    font  = _font(26, bold=False)
    x     = gx
    for i, g in enumerate(items):
        gw = int(draw.textlength(g, font=font))
        if x + gw > gx + max_w:
            break
        draw.text((x, gy), g, font=font, fill=(225, 225, 225, 220))
        x += gw + 12
        if i < len(items) - 1:
            draw.text((x - 6, gy), "•", font=font, fill=(170, 170, 170, 200))
            x += 18


def _build_card(
    poster: Image.Image,
    backdrop: Optional[Image.Image],
    watermark: str,
    meta: dict,
) -> Image.Image:
    W, H = _SIZE

    # ── Base with brighter backdrop ──────────────────────────────────────────
    canvas = Image.new("RGBA", (W, H), (14, 14, 20, 255))

    bg = (backdrop or poster).convert("RGBA").resize((W, H), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(9))
    bg = ImageEnhance.Brightness(bg).enhance(0.48)     # brighter image
    bg = ImageEnhance.Contrast(bg).enhance(1.12)
    canvas.paste(bg, (0, 0))

    # ── Right-side character art ─────────────────────────────────────────────
    char_img = poster.convert("RGBA")
    char_h   = int(H * 0.92)               # smaller scale → more balanced
    char_w   = int(char_h * char_img.width / char_img.height)
    char_img = char_img.resize((char_w, char_h), Image.LANCZOS)

    char_x = W - char_w + int(char_w * 0.06)  # slight overlap for dynamic feel
    char_y = -int(H * 0.02)

    # Very soft left fade (more visible character)
    fade_w = int(char_w * 0.30)
    for i in range(fade_w):
        alpha = int(255 * (i / fade_w) ** 0.9)  # very gentle
        for yy in range(char_img.height):
            r,g,b,a = char_img.getpixel((i, yy))
            char_img.putpixel((i, yy), (r,g,b, min(a, alpha)))

    # Almost no bottom fade
    fade_bot = int(char_h * 0.08)
    for j in range(fade_bot):
        alpha = int(255 * (j / fade_bot) ** 1.0)
        yy = char_h - fade_bot + j
        if yy < char_h:
            for xi in range(char_w):
                r,g,b,a = char_img.getpixel((xi, yy))
                char_img.putpixel((xi, yy), (r,g,b, min(a, alpha)))

    canvas.paste(char_img, (char_x, char_y), char_img)

    # ── Very soft left gradient ──────────────────────────────────────────────
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(grad)
    for i in range(int(W * 0.50)):  # narrower zone
        alpha = max(0, int(110 - (i / (W*0.50)) * 130))  # much lighter
        gd.line([(i, 0), (i, H)], fill=(8, 8, 14, alpha))
    canvas = Image.alpha_composite(canvas, grad)

    draw = ImageDraw.Draw(canvas)

    title    = meta.get("title", "").upper()
    genres   = meta.get("genres", "")
    overview = meta.get("overview") or meta.get("synopsis", "")
    category = meta.get("_category", "")

    left_x   = 80
    title_y  = 140
    text_w   = int(W * 0.50)

    # ── Genres ────────────────────────────────────────────────────────────────
    _draw_genre_tags(draw, genres, left_x, 90, text_w)

    # ── Title ─────────────────────────────────────────────────────────────────
    tf    = _font(74)
    tlines = _wrap(title, tf, draw, text_w)[:3]
    y     = title_y
    for ln in tlines:
        draw.text((left_x+4, y+4), ln, font=tf, fill=(0,0,0,160))   # shadow
        draw.text((left_x, y), ln, font=tf, fill=(255, 255, 255, 255))
        y += 84

    y += 24

    # ── Overview ──────────────────────────────────────────────────────────────
    if overview:
        df = _font(27, bold=False)
        lines = _wrap(overview, df, draw, text_w)[:4]
        for ln in lines:
            draw.text((left_x, y), ln, font=df, fill=(210, 210, 225, 235))
            y += 38
    y += 35

    # ── Premium buttons ───────────────────────────────────────────────────────
    btn_font = _font(28, bold=True)
    btn_h    = 72
    btn_pad  = 50
    btn_gap  = 24

    # DOWNLOAD button — premium outline + gradient
    dl_label = "DOWNLOAD"
    dl_w     = int(draw.textlength(dl_label, font=btn_font)) + btn_pad * 2
    dl_x     = left_x
    dl_y     = y

    # Shadow
    draw.rounded_rectangle([dl_x+5, dl_y+5, dl_x+dl_w+5, dl_y+btn_h+5], radius=36, fill=(0,0,0,120))

    # Gradient bg
    for i in range(btn_h):
        a = 200 + int((i / btn_h) * 55)
        draw.line([(dl_x, dl_y+i), (dl_x+dl_w, dl_y+i)], fill=(50,50,70,a))

    draw.rounded_rectangle([dl_x, dl_y, dl_x+dl_w, dl_y+btn_h], radius=36,
                           outline=(160,160,220,220), width=4)
    dl_tx = dl_x + (dl_w - int(draw.textlength(dl_label, font=btn_font))) // 2
    draw.text((dl_tx, dl_y + 20), dl_label, font=btn_font, fill=(240, 240, 255, 255))

    # WATCH NOW — bold red premium
    wn_label = "WATCH NOW"
    wn_w     = int(draw.textlength(wn_label, font=btn_font)) + btn_pad * 2
    wn_x     = dl_x + dl_w + btn_gap
    wn_y     = y

    # Shadow
    draw.rounded_rectangle([wn_x+6, wn_y+6, wn_x+wn_w+6, wn_y+btn_h+6], radius=36, fill=(0,0,0,140))

    # Red gradient
    for i in range(btn_h):
        r = 220 - int(i / btn_h * 40)
        draw.line([(wn_x, wn_y+i), (wn_x+wn_w, wn_y+i)], fill=(r, 40, 40, 255))

    draw.rounded_rectangle([wn_x, wn_y, wn_x+wn_w, wn_y+btn_h], radius=36, fill=(220, 45, 45, 255))
    wn_tx = wn_x + (wn_w - int(draw.textlength(wn_label, font=btn_font))) // 2
    draw.text((wn_tx, wn_y + 20), wn_label, font=btn_font, fill=(255, 255, 255, 255))

    # ── Episode card (smaller, cleaner) ──────────────────────────────────────
    card_w, card_h = 300, 100
    card_x = W - card_w - 50
    card_y = H - card_h - 50

    card = Image.new("RGBA", (card_w, card_h), (0,0,0,0))
    cd   = ImageDraw.Draw(card)
    cd.rounded_rectangle([0,0,card_w,card_h], radius=18, fill=(18,18,28,210))
    cd.rounded_rectangle([0,0,card_w,card_h], radius=18, outline=(80,80,100,160), width=2)

    thumb_w, thumb_h = 80, card_h - 20
    thumb_x = card_w - thumb_w - 12
    thumb_y = 10
    if backdrop or poster:
        th_img = (backdrop or poster).convert("RGBA").resize((thumb_w, thumb_h), Image.LANCZOS)
        th_mask = Image.new("L", (thumb_w, thumb_h), 0)
        ImageDraw.Draw(th_mask).rounded_rectangle([0,0,thumb_w,thumb_h], radius=12, fill=255)
        card.paste(th_img, (thumb_x, thumb_y), th_mask)

    ep_num  = f"Ep. {episodes.zfill(2) if episodes and episodes.isdigit() else '??'}"
    cd.text((16, 16), ep_num, font=_font(30), fill=(255,255,255,255))

    rt_text = runtime or ("~24m" if category in ("anime", "tvshow") else "")
    if rt_text:
        cd.text((16, 58), f"Duration • {rt_text}", font=_font(22, bold=False), fill=(200,200,220,220))

    canvas.paste(card, (card_x, card_y), card)

    # ── Watermark ─────────────────────────────────────────────────────────────
    canvas = _draw_logo_watermark(canvas, watermark)

    return canvas.convert("RGB")


async def build_thumbnail(
    poster_url: Optional[str] = None,
    backdrop_url: Optional[str] = None,
    watermark: str = "",
    meta: dict = {},
) -> bytes:
    os.makedirs("temp", exist_ok=True)
    poster   = await _fetch(poster_url) if poster_url else None
    backdrop = await _fetch(backdrop_url) if backdrop_url else None

    if poster is None:
        poster = Image.new("RGBA", (400, 600), (30, 30, 42, 255))
        ImageDraw.Draw(poster).text((60, 280), "No Image", fill=(120,120,140), font=_font(28))

    card = _build_card(poster, backdrop, watermark, meta)
    buf  = io.BytesIO()
    card.save(buf, format="JPEG", quality=94, optimize=True)
    return buf.getvalue()


async def process_custom_thumbnail(photo_bytes: bytes, watermark: str = "") -> bytes:
    img = Image.open(io.BytesIO(photo_bytes)).convert("RGBA").resize(_SIZE, Image.LANCZOS)
    canvas = _draw_logo_watermark(img.convert("RGBA"), watermark)
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="JPEG", quality=94, optimize=True)
    return buf.getvalue()