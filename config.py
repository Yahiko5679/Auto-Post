"""
CosmicBotz — Configuration
All values loaded from environment / .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────────────
API_ID       = int(os.getenv("API_ID", "0"))
API_HASH     = os.getenv("API_HASH", "")
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "CosmicBotz")

# ── Admins ────────────────────────────────────────────────────────────────────
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "0").split(",") if x.strip()]

# ── Database ──────────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
REDIS_URL  = os.getenv("REDIS_URL", "")

# ── External APIs ─────────────────────────────────────────────────────────────
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
IMDB_API_KEY = os.getenv("IMDB_API_KEY", "")   # RapidAPI IMDb (optional)
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "")   # OMDb fallback  (optional)

TMDB_BASE_URL  = "https://api.themoviedb.org/3"
TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/w500"
JIKAN_BASE_URL = "https://api.jikan.moe/v4"
ANILIST_URL    = "https://graphql.anilist.co"

# ── Limits ────────────────────────────────────────────────────────────────────
FREE_POSTS_PER_DAY    = int(os.getenv("FREE_POSTS_PER_DAY",    "10"))
PREMIUM_POSTS_PER_DAY = int(os.getenv("PREMIUM_POSTS_PER_DAY", "999"))
MAX_SEARCH_RESULTS    = int(os.getenv("MAX_SEARCH_RESULTS",    "5"))

# ── Web server (Render keep-alive) ────────────────────────────────────────────
PORT = int(os.getenv("PORT", "8080"))

# ── Paths ─────────────────────────────────────────────────────────────────────
FONTS_DIR = "assets/fonts"
TEMP_DIR  = "temp"

# ── Default caption templates ─────────────────────────────────────────────────
DEFAULT_MOVIE_FORMAT = """\
🎬 **{title}** ({year})

┌ 🌐 **Audio**     » {audio}
├ 🎞 **Quality**   » {quality}
├ ⭐ **IMDb**       » {imdb_rating}/10 ({imdb_votes})
├ 🎭 **Genre**     » {genres}
├ 🔞 **Rated**     » {content_rating}
├ ⏱ **Runtime**   » {runtime}
└ 🗓 **Released**  » {release_date}

📝 {overview}

{hashtags}"""

DEFAULT_TV_FORMAT = """\
📺 **{title}** ({year})

┌ 🌐 **Audio**     » {audio}
├ 🎞 **Quality**   » {quality}
├ ⭐ **IMDb**       » {imdb_rating}/10 ({imdb_votes})
├ 🎭 **Genre**     » {genres}
├ 📡 **Status**    » {status}
├ 🗓 **Seasons**   » {seasons}
├ 📋 **Episodes**  » {episodes}
└ 🏢 **Network**   » {network}

📝 {overview}

{hashtags}"""

DEFAULT_ANIME_FORMAT = """\
🌸 **{title}**

┌ 📌 **Type**      » {type}
├ ⭐ **Rating**     » {rating}%
├ 📡 **Status**    » {status}
├ 📋 **Episodes**  » {episodes}
├ 🎭 **Genre**     » {genres}
├ 🎙 **Studio**    » {studio}
└ 🗓 **Aired**     » {aired}

📝 {synopsis}

{hashtags}"""

DEFAULT_MANHWA_FORMAT = """\
📖 **{title}**

┌ 📌 **Type**      » {type}
├ ⭐ **Rating**     » {rating}%
├ 📡 **Status**    » {status}
├ 📚 **Chapters**  » {chapters}
├ 🎭 **Genre**     » {genres}
└ 🗓 **Published** » {published}

📝 {synopsis}

{hashtags}"""

DEFAULT_QUALITY = "480p | 720p | 1080p"
DEFAULT_AUDIO   = "Hindi | English"
