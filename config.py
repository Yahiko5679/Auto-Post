import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
ADMIN_IDS    = [int(x) for x in os.getenv("ADMIN_IDS", "0").split(",") if x.strip()]
WEBHOOK_URL  = os.getenv("WEBHOOK_URL", "")

# Database
MONGO_URI    = os.getenv("MONGO_URI", "mongodb://localhost:27017")
REDIS_URL    = os.getenv("REDIS_URL", "")

# APIs
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
IMDB_API_KEY = os.getenv("IMDB_API_KEY", "")
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "")

TMDB_BASE_URL  = "https://api.themoviedb.org/3"
TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/w500"
JIKAN_BASE_URL = "https://api.jikan.moe/v4"
ANILIST_URL    = "https://graphql.anilist.co"

# Limits
FREE_POSTS_PER_DAY    = int(os.getenv("FREE_POSTS_PER_DAY", "10"))
PREMIUM_POSTS_PER_DAY = int(os.getenv("PREMIUM_POSTS_PER_DAY", "999"))
MAX_SEARCH_RESULTS    = int(os.getenv("MAX_SEARCH_RESULTS", "5"))

# Server
PORT = int(os.getenv("PORT", "8080"))

# Defaults
DEFAULT_QUALITY = "480p | 720p | 1080p"
DEFAULT_AUDIO   = "Hindi | English"
FONTS_DIR = "assets/fonts"
TEMP_DIR  = "temp"

DEFAULT_MOVIE_FORMAT = """\
🎬 <b>{title}</b> ({year})

┌ 🌐 <b>Audio</b>     » {audio}
├ 🎞 <b>Quality</b>   » {quality}
├ ⭐ <b>IMDb</b>       » {imdb_rating}/10 ({imdb_votes})
├ 🎭 <b>Genre</b>     » {genres}
├ 🔞 <b>Rated</b>     » {content_rating}
├ ⏱ <b>Runtime</b>   » {runtime}
└ 🗓 <b>Released</b>  » {release_date}

📝 {overview}

{hashtags}"""

DEFAULT_TV_FORMAT = """\
📺 <b>{title}</b> ({year})

┌ 🌐 <b>Audio</b>     » {audio}
├ 🎞 <b>Quality</b>   » {quality}
├ ⭐ <b>IMDb</b>       » {imdb_rating}/10 ({imdb_votes})
├ 🎭 <b>Genre</b>     » {genres}
├ 📡 <b>Status</b>    » {status}
├ 🗓 <b>Seasons</b>   » {seasons}
├ 📋 <b>Episodes</b>  » {episodes}
└ 🏢 <b>Network</b>   » {network}

📝 {overview}

{hashtags}"""

DEFAULT_ANIME_FORMAT = """\
🌸 <b>{title}</b>

┌ 📌 <b>Type</b>      » {type}
├ ⭐ <b>Rating</b>     » {rating}%
├ 📡 <b>Status</b>    » {status}
├ 📋 <b>Episodes</b>  » {episodes}
├ 🎭 <b>Genre</b>     » {genres}
├ 🎙 <b>Studio</b>    » {studio}
└ 🗓 <b>Aired</b>     » {aired}

📝 {synopsis}

{hashtags}"""

DEFAULT_MANHWA_FORMAT = """\
📖 <b>{title}</b>

┌ 📌 <b>Type</b>      » {type}
├ ⭐ <b>Rating</b>     » {rating}%
├ 📡 <b>Status</b>    » {status}
├ 📚 <b>Chapters</b>  » {chapters}
├ 🎭 <b>Genre</b>     » {genres}
└ 🗓 <b>Published</b> » {published}

📝 {synopsis}

{hashtags}"""
