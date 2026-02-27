"""
Configuration
━━━━━━━━━━━━━
Reads all values from environment variables.
Copy .env.example → .env and fill in secrets for local dev.
On Render, set env vars in the Dashboard or render.yaml.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Bot Credentials ────────────────────────────────────────────────────────────
BOT_TOKEN    = os.getenv("BOT_TOKEN",    "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")

# ── Admin IDs (comma-separated Telegram user IDs) ─────────────────────────────
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# ── TMDb ──────────────────────────────────────────────────────────────────────
TMDB_API_KEY   = os.getenv("TMDB_API_KEY",   "")
TMDB_BASE_URL  = "https://api.themoviedb.org/3"
TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/w500"

# ── IMDb (optional — enriches ratings, box office, awards) ────────────────────
# Option A: RapidAPI IMDb  →  https://rapidapi.com/apidojo/api/imdb8
IMDB_API_KEY  = os.getenv("IMDB_API_KEY",  "")   # RapidAPI key
# Option B: OMDb fallback  →  https://www.omdbapi.com/
OMDB_API_KEY  = os.getenv("OMDB_API_KEY",  "")   # OMDb API key

# ── Jikan (MyAnimeList) — no key needed ───────────────────────────────────────
JIKAN_BASE_URL = "https://api.jikan.moe/v4"

# ── AniList GraphQL — no key needed ───────────────────────────────────────────
ANILIST_URL = "https://graphql.anilist.co"

# ── MongoDB ────────────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME   = "autopost_bot"

# ── Redis (FSM state) — falls back to in-memory if not set ────────────────────
REDIS_URL = os.getenv("REDIS_URL", "")

# ── Webhook / Server (Render) ─────────────────────────────────────────────────
MODE         = os.getenv("MODE", "")       # "webhook" | "polling"
PORT         = int(os.getenv("PORT", 8080))
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
# Auto-built from RENDER_EXTERNAL_URL in webserver.py

# ── Paths ──────────────────────────────────────────────────────────────────────
ASSETS_DIR   = "assets"
FONTS_DIR    = "assets/fonts"
OVERLAYS_DIR = "assets/overlays"
TEMP_DIR     = "temp"

# ── Bot Limits ─────────────────────────────────────────────────────────────────
FREE_POSTS_PER_DAY    = int(os.getenv("FREE_POSTS_PER_DAY",    10))
PREMIUM_POSTS_PER_DAY = int(os.getenv("PREMIUM_POSTS_PER_DAY", 999))
MAX_SEARCH_RESULTS    = int(os.getenv("MAX_SEARCH_RESULTS",    5))

# ── Default Post Format Templates ─────────────────────────────────────────────
# Supports all tokens including new IMDb ones:
# {imdb_rating} {imdb_votes} {imdb_url} {content_rating}
# {box_office}  {awards}     {metacritic}

DEFAULT_MOVIE_FORMAT = """\
🎬 {title} ({year})

┌─ 🌐 Audio        » {audio}
├─ 🎞️ Quality      » {quality}
├─ ⭐ IMDb          » {imdb_rating}/10 ({imdb_votes} votes)
├─ 🎭 Genre        » {genres}
├─ 🔞 Rating       » {content_rating}
├─ ⏱️ Runtime      » {runtime}
└─ 🗓️ Released     » {release_date}

📝 {overview}

{hashtags}
"""

DEFAULT_TV_FORMAT = """\
📺 {title} ({year})

┌─ 🌐 Audio        » {audio}
├─ 🎞️ Quality      » {quality}
├─ ⭐ IMDb          » {imdb_rating}/10 ({imdb_votes} votes)
├─ 🎭 Genre        » {genres}
├─ 📡 Status       » {status}
├─ 🗓️ Seasons      » {seasons}
├─ 📋 Episodes     » {episodes}
└─ 🏢 Network      » {network}

📝 {overview}

{hashtags}
"""

DEFAULT_ANIME_FORMAT = """\
🌸 {title}

┌─ 📌 Type         » {type}
├─ ⭐ MAL Rating    » {rating}%
├─ 📡 Status       » {status}
├─ 📋 Episodes     » {episodes}
├─ 🎭 Genre        » {genres}
├─ 🎙️ Studio       » {studio}
└─ 🗓️ Aired        » {aired}

📝 {synopsis}

{hashtags}
"""

DEFAULT_MANHWA_FORMAT = """\
📖 {title}

┌─ 📌 Type         » {type}
├─ ⭐ Rating        » {rating}%
├─ 📡 Status       » {status}
├─ 📚 Chapters     » {chapters}
├─ 🎭 Genre        » {genres}
└─ 🗓️ Published    » {published}

📝 {synopsis}

{hashtags}
"""

# ── Quality / Audio Defaults ───────────────────────────────────────────────────
DEFAULT_QUALITY = "480p | 720p | 1080p"
DEFAULT_AUDIO   = "Hindi | English"
