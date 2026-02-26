# 🤖 AutoPost Generator Bot

A full-featured Telegram bot for generating beautiful, ready-to-post content for Movies, TV Shows, Anime, and Manhwa — with custom templates, watermarking, and direct channel posting.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎬 Movies | Fetches from TMDb — poster, rating, genres, overview |
| 📺 TV Shows | Seasons, episodes, network, status |
| 🌸 Anime | MAL data via Jikan — episodes, studio, aired |
| 📖 Manhwa/Manga | AniList — chapters, status, type (MANHWA/MANGA/MANHUA) |
| 🖼 Thumbnails | Auto-generated 1280×720 cards with blurred backdrop |
| 🖋 Watermarks | Custom text overlay on every thumbnail |
| 📋 Templates | Full custom format builder with token system |
| 📺 Channel Post | Post directly to your Telegram channel |
| 👑 Admin Panel | Broadcast, ban, premium management, global stats |
| ⭐ Premium | Daily limit for free users, unlimited for premium |

---

## 🚀 Quick Setup

### 1. Clone & Configure
```bash
git clone <repo>
cd autopost_bot
cp .env.example .env
# Edit .env with your tokens
```

### 2. Get API Keys
- **Bot Token**: [@BotFather](https://t.me/botfather) → `/newbot`
- **TMDb Key**: https://www.themoviedb.org/settings/api (free)
- Jikan (anime) and AniList (manhwa) require **no API key**

### 3. Run with Docker (recommended)
```bash
docker-compose up -d
```

### 3b. Run Locally
```bash
pip install -r requirements.txt
mkdir -p assets/fonts temp
# Copy a font: cp /path/to/DejaVuSans-Bold.ttf assets/fonts/
python main.py
```

---

## 💬 Commands

### Content
```
/movie <title>     — Generate movie post
/tvshow <title>    — Generate TV show post
/anime <title>     — Generate anime post
/manhwa <title>    — Generate manhwa post
```

### Customization
```
/settings          — Open settings panel
/setformat         — Build a custom post template
/templates         — Manage your templates
/myformat          — View active template
/setwatermark      — Set thumbnail watermark
/setchannel        — Link your channel
/stats             — Your usage stats
```

### Admin Only
```
/admin             — Admin panel
/broadcast         — Send message to all users
/ban <id>          — Ban a user
/unban <id>        — Unban a user
/addpremium <id>   — Grant premium
/revokepremium <id>— Revoke premium
/userinfo <id>     — View user details
/globalstats       — Global usage stats
```

---

## 📋 Template System

Build custom post formats using token substitution.

### Available Tokens

**Movies & TV:** `{title}` `{year}` `{rating}` `{genres}` `{overview}` `{quality}` `{audio}` `{release_date}` `{runtime}` `{status}` `{seasons}` `{episodes}` `{network}` `{language}` `{hashtags}`

**Anime:** `{title}` `{title_jp}` `{rating}` `{genres}` `{synopsis}` `{status}` `{episodes}` `{type}` `{aired}` `{studio}` `{source}` `{season}` `{hashtags}`

**Manhwa:** `{title}` `{title_native}` `{rating}` `{genres}` `{synopsis}` `{status}` `{chapters}` `{volumes}` `{type}` `{published}` `{hashtags}`

### Example Template
```
🎬 {title} ({year})

⭐ {rating}/10  |  🎭 {genres}
🔊 {audio}  |  🎞 {quality}

📝 {overview}

{hashtags}
```

---

## 🗂 Project Structure

```
autopost_bot/
├── main.py                 # Bot entry, handler registration
├── config.py               # All configuration & defaults
├── handlers/
│   ├── base.py             # Shared search→preview→post flow
│   ├── movie.py            # Movie handler
│   ├── tvshow.py           # TV show handler
│   ├── anime.py            # Anime handler
│   ├── manhwa.py           # Manhwa handler
│   ├── start.py            # /start, /help, /stats
│   ├── settings.py         # Settings panel
│   ├── template.py         # Template builder
│   └── admin.py            # Admin panel
├── fetchers/
│   ├── tmdb.py             # TMDb API (movies + TV)
│   ├── jikan.py            # Jikan API (anime/MAL)
│   └── anilist.py          # AniList GraphQL (manhwa)
├── formatter/
│   └── engine.py           # Template render engine
├── thumbnail/
│   └── processor.py        # Pillow image processing
├── database/
│   └── db.py               # MongoDB motor async layer
├── fsm/
│   ├── state_manager.py    # Redis-backed FSM
│   └── states.py           # State constants
├── utils/
│   ├── keyboards.py        # InlineKeyboard builders
│   └── helpers.py          # Decorators, shared utils
├── assets/fonts/           # Put DejaVuSans-Bold.ttf here
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## 🔧 Architecture

```
User → /movie inception
         ↓
    TMDb Search → Results list
         ↓
    User selects result
         ↓
    TMDb Detail fetch
         ↓
    FSM: awaiting_thumbnail
         ↓ (upload or skip)
    Thumbnail Processor (Pillow)
         ↓
    Format Engine renders caption
         ↓
    Preview (photo + caption + buttons)
         ↓
    [Post to Channel] or [Copy Caption]
```

---

## ⚡ Post Flow

1. User types `/anime solo leveling`
2. Bot searches Jikan → shows up to 5 results
3. User taps a result → bot fetches full details
4. Bot asks for custom thumbnail (or skip)
5. Bot builds 1280×720 thumbnail card with watermark
6. Bot renders caption using user's active template
7. Preview shown with action buttons
8. User posts to channel or copies caption

---

## 🏗 Tech Stack

- **python-telegram-bot** v21 (async)
- **MongoDB + motor** (user data, templates)
- **Redis** (FSM state, falls back to memory)
- **Pillow** (thumbnail generation)
- **aiohttp** (all external API calls)
- **TMDb** · **Jikan** · **AniList** (data sources)
