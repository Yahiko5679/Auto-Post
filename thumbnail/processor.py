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

_FONT_PATH  = "assets/fonts/DejaVuSans-Bold.ttf"
_SIZE       = (1280, 720)


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
    draw  = ImageDraw.Draw(img)
    font  = _font(26)
    W, H  = img.size
    bbox  = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    m  = 14
    x  = W - tw - m * 2 - 10
    y  = H - th - m * 2 - 10
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.rounded_rectangle([x, y, x + tw + m*2, y + th + m*2], radius=8, fill=(0, 0, 0, 160))
    od.text((x + m, y + m), text, font=font, fill=(255, 255, 255, 230))
    return Image.alpha_composite(img, ov)


def _build_card(poster: Image.Image, backdrop: Optional[Image.Image], watermark: str) -> Image.Image:
    W, H = _SIZE
    canvas = Image.new("RGBA", (W, H), (15, 15, 20, 255))

    # Background: blurred backdrop or poster
    bg = (backdrop or poster).convert("RGBA").resize((W, H), Image.LANCZOS)
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(18))).enhance(0.45)
    canvas.paste(bg, (0, 0))

    # Gradient overlay
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(grad)
    for i in range(W):
        gd.line([(i, 0), (i, H)], fill=(0, 0, 0, int(80 + (i / W) * 120)))
    canvas = Image.alpha_composite(canvas, grad)

    # Poster
    ph = int(H * 0.82)
    pw = int(ph * 2 / 3)
    px, py = 60, (H - ph) // 2
    pr = poster.convert("RGBA").resize((pw, ph), Image.LANCZOS)

    # Shadow
    sh = Image.new("RGBA", (pw + 20, ph + 20), (0, 0, 0, 0))
    sb = Image.new("RGBA", (pw + 20, ph + 20), (0, 0, 0, 180))
    canvas.paste(sb.filter(ImageFilter.GaussianBlur(10)), (px - 5, py + 5), sb.filter(ImageFilter.GaussianBlur(10)))

    # Rounded poster
    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw, ph], radius=12, fill=255)
    canvas.paste(pr, (px, py), mask)

    # Accent line
    ImageDraw.Draw(canvas).line(
        [(px + pw + 20, py + 10), (px + pw + 20, py + ph - 10)],
        fill=(255, 200, 50, 180), width=3,
    )

    return _watermark(canvas, watermark).convert("RGB")


async def build_thumbnail(
    poster_url: Optional[str],
    backdrop_url: Optional[str] = None,
    watermark: str = "",
) -> bytes:
    """Download images and build a 1280x720 card. Returns JPEG bytes."""
    os.makedirs("temp", exist_ok=True)

    poster = (await _fetch(poster_url)) if poster_url else None
    if poster is None:
        poster = Image.new("RGBA", (400, 600), (30, 30, 40, 255))
        ImageDraw.Draw(poster).text((20, 280), "No Image", fill=(200, 200, 200), font=_font(24))

    backdrop = (await _fetch(backdrop_url)) if backdrop_url else None
    card = _build_card(poster, backdrop, watermark)

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
