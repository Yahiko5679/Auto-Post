"""
Thumbnail Processor
- Downloads poster from URL
- Applies watermark text overlay
- Composites custom user image
- Outputs final PIL Image as bytes
"""

import io
import os
import logging
import aiohttp
import asyncio
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

logger = logging.getLogger(__name__)

FONT_PATH = "assets/fonts/DejaVuSans-Bold.ttf"
FALLBACK_FONT_SIZE = 28
THUMBNAIL_SIZE = (1280, 720)  # 16:9 output
POSTER_CROP_RATIO = (2, 3)


async def download_image(url: str) -> Optional[Image.Image]:
    """Download an image from URL and return PIL Image."""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    data = await r.read()
                    return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception as e:
        logger.error(f"Image download failed: {e}")
    return None


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


def _add_watermark(img: Image.Image, text: str) -> Image.Image:
    """Add semi-transparent watermark text to bottom-right corner."""
    if not text:
        return img
    draw = ImageDraw.Draw(img.copy())
    font = _load_font(26)
    w, h = img.size

    # Measure text
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Watermark background pill
    margin = 14
    x = w - tw - margin * 2 - 10
    y = h - th - margin * 2 - 10

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(
        [x, y, x + tw + margin * 2, y + th + margin * 2],
        radius=8,
        fill=(0, 0, 0, 160),
    )
    od.text((x + margin, y + margin), text, font=font, fill=(255, 255, 255, 230))

    result = Image.alpha_composite(img, overlay)
    return result


def _create_banner_card(
    poster: Image.Image,
    banner: Optional[Image.Image],
    watermark: str = "",
) -> Image.Image:
    """
    Create a 1280×720 thumbnail card:
    - Blurred banner/backdrop as background
    - Poster (portrait) on left
    - Right side empty (for caption overlay or channel branding)
    """
    W, H = THUMBNAIL_SIZE
    canvas = Image.new("RGBA", (W, H), (15, 15, 20, 255))

    # Background: blurred banner or stretched poster
    if banner:
        bg = banner.convert("RGBA").resize((W, H), Image.LANCZOS)
    else:
        bg = poster.convert("RGBA").resize((W, H), Image.LANCZOS)

    bg = bg.filter(ImageFilter.GaussianBlur(radius=18))
    bg = ImageEnhance.Brightness(bg).enhance(0.45)
    canvas.paste(bg, (0, 0))

    # Dark gradient overlay (left side lighter)
    gradient = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gradient)
    for i in range(W):
        alpha = int(80 + (i / W) * 120)
        gd.line([(i, 0), (i, H)], fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas, gradient)

    # Poster card
    poster_h = int(H * 0.82)
    poster_w = int(poster_h * 2 / 3)
    poster_x = 60
    poster_y = (H - poster_h) // 2

    poster_resized = poster.convert("RGBA").resize((poster_w, poster_h), Image.LANCZOS)

    # Drop shadow
    shadow = Image.new("RGBA", (poster_w + 20, poster_h + 20), (0, 0, 0, 0))
    shadow_bg = Image.new("RGBA", (poster_w + 20, poster_h + 20), (0, 0, 0, 180))
    shadow_bg = shadow_bg.filter(ImageFilter.GaussianBlur(radius=10))
    canvas.paste(shadow_bg, (poster_x - 5, poster_y + 5), shadow_bg)

    # Rounded corners on poster
    mask = Image.new("L", (poster_w, poster_h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, poster_w, poster_h], radius=12, fill=255)
    canvas.paste(poster_resized, (poster_x, poster_y), mask)

    # Thin accent line
    accent = ImageDraw.Draw(canvas)
    accent.line(
        [(poster_x + poster_w + 20, poster_y + 10),
         (poster_x + poster_w + 20, poster_y + poster_h - 10)],
        fill=(255, 200, 50, 180), width=3
    )

    # Watermark
    if watermark:
        canvas = _add_watermark(canvas, watermark)

    return canvas.convert("RGB")


async def build_thumbnail(
    poster_url: Optional[str],
    backdrop_url: Optional[str] = None,
    watermark: str = "",
    custom_image: Optional[bytes] = None,
) -> bytes:
    """
    Build final thumbnail and return as JPEG bytes.
    If custom_image is provided, use it as poster.
    """
    os.makedirs("temp", exist_ok=True)

    # Poster source
    if custom_image:
        poster = Image.open(io.BytesIO(custom_image)).convert("RGBA")
    elif poster_url:
        poster = await download_image(poster_url)
    else:
        poster = None

    if poster is None:
        # Fallback: solid colored card
        poster = Image.new("RGBA", (400, 600), (30, 30, 40, 255))
        d = ImageDraw.Draw(poster)
        d.text((20, 280), "No Image", fill=(200, 200, 200, 255), font=_load_font(24))

    # Backdrop
    backdrop = None
    if backdrop_url:
        backdrop = await download_image(backdrop_url)

    canvas = _create_banner_card(poster, backdrop, watermark)

    # Encode to JPEG bytes
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()


async def process_custom_thumbnail(
    photo_bytes: bytes,
    watermark: str = "",
) -> bytes:
    """
    Process a user-uploaded custom thumbnail.
    Resize to 1280×720 and apply watermark if set.
    """
    img = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
    img = img.resize(THUMBNAIL_SIZE, Image.LANCZOS)
    if watermark:
        img = _add_watermark(img, watermark)
    img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()
