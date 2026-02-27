"""
Format Template Engine
Renders metadata into beautiful post captions.
Supports all tokens including new IMDb-sourced fields.
"""

import re
import logging
from typing import Dict, Optional
from config import (
    DEFAULT_MOVIE_FORMAT, DEFAULT_TV_FORMAT,
    DEFAULT_ANIME_FORMAT, DEFAULT_MANHWA_FORMAT,
    DEFAULT_QUALITY, DEFAULT_AUDIO,
)

logger = logging.getLogger(__name__)


class FormatEngine:
    DEFAULT_TEMPLATES = {
        "movie":  DEFAULT_MOVIE_FORMAT,
        "tvshow": DEFAULT_TV_FORMAT,
        "anime":  DEFAULT_ANIME_FORMAT,
        "manhwa": DEFAULT_MANHWA_FORMAT,
    }

    # Full token reference shown to users in /setformat help
    TOKEN_DOCS = {
        "movie": [
            "{title}", "{year}", "{release_date}", "{runtime}", "{language}",
            "{rating}", "{imdb_rating}", "{imdb_votes}", "{imdb_url}",
            "{content_rating}", "{box_office}", "{awards}", "{metacritic}",
            "{genres}", "{overview}", "{status}", "{tagline}",
            "{audio}", "{quality}", "{hashtags}",
        ],
        "tvshow": [
            "{title}", "{year}", "{release_date}", "{language}",
            "{rating}", "{imdb_rating}", "{imdb_votes}", "{imdb_url}",
            "{content_rating}", "{awards}", "{metacritic}",
            "{genres}", "{overview}", "{status}",
            "{seasons}", "{episodes}", "{network}",
            "{audio}", "{quality}", "{hashtags}",
        ],
        "anime": [
            "{title}", "{title_jp}", "{year}", "{rating}",
            "{genres}", "{synopsis}", "{status}", "{episodes}",
            "{type}", "{aired}", "{studio}", "{source}", "{season}",
            "{hashtags}",
        ],
        "manhwa": [
            "{title}", "{title_native}", "{year}", "{rating}",
            "{genres}", "{synopsis}", "{status}", "{chapters}",
            "{volumes}", "{type}", "{published}", "{hashtags}",
        ],
    }

    def render(
        self,
        category: str,
        metadata: Dict,
        template: Optional[str] = None,
        user_settings: Optional[Dict] = None,
    ) -> str:
        tpl = template or self.DEFAULT_TEMPLATES.get(category, "{title}")
        user_settings = user_settings or {}
        tokens = self._build_tokens(category, metadata, user_settings)
        return self._substitute(tpl, tokens)

    def _build_tokens(self, category: str, meta: Dict, settings: Dict) -> Dict:
        quality = settings.get("quality") or DEFAULT_QUALITY
        audio   = settings.get("audio")   or DEFAULT_AUDIO
        title   = meta.get("title", "Unknown")

        raw_genres = meta.get("genres", "") or ""
        hashtags   = self._make_hashtags(title, category, raw_genres)

        # ── IMDb fields (shared by movie + tvshow) ─────────────────────────────
        imdb_rating = meta.get("imdb_rating")
        imdb_str    = f"{imdb_rating}" if imdb_rating else str(meta.get("rating", "N/A"))
        rating_src  = meta.get("rating_src", "TMDb")

        base = {
            "title":          title,
            "year":           meta.get("year", ""),
            "rating":         meta.get("rating", "N/A"),
            "imdb_rating":    imdb_str,
            "imdb_votes":     meta.get("imdb_votes", "N/A"),
            "imdb_url":       meta.get("imdb_url", ""),
            "content_rating": meta.get("content_rating", "N/A"),
            "box_office":     meta.get("box_office", "N/A"),
            "awards":         meta.get("awards", "N/A"),
            "metacritic":     meta.get("metacritic", "N/A"),
            "genres":         raw_genres,
            "quality":        quality,
            "audio":          audio,
            "hashtags":       hashtags,
        }

        if category == "movie":
            base.update({
                "release_date": meta.get("release_date", "N/A"),
                "overview":     meta.get("overview", "N/A"),
                "runtime":      meta.get("runtime", "N/A"),
                "status":       meta.get("status", "N/A"),
                "tagline":      meta.get("tagline", ""),
                "language":     meta.get("language", "N/A"),
            })

        elif category == "tvshow":
            base.update({
                "release_date": meta.get("release_date", "N/A"),
                "overview":     meta.get("overview", "N/A"),
                "status":       meta.get("status", "N/A"),
                "seasons":      meta.get("seasons", "N/A"),
                "episodes":     meta.get("episodes", "N/A"),
                "network":      meta.get("network", "N/A"),
                "language":     meta.get("language", "N/A"),
            })

        elif category == "anime":
            base.update({
                "title_jp":  meta.get("title_jp", ""),
                "synopsis":  meta.get("synopsis", "N/A"),
                "status":    meta.get("status", "N/A"),
                "episodes":  meta.get("episodes", "?"),
                "type":      meta.get("type", "TV"),
                "aired":     meta.get("aired", "N/A"),
                "studio":    meta.get("studio", "N/A"),
                "source":    meta.get("source", "N/A"),
                "season":    meta.get("season", "N/A"),
            })
            r = meta.get("rating", 0)
            base["rating"] = f"{r}%" if isinstance(r, int) else str(r)

        elif category == "manhwa":
            base.update({
                "title_native": meta.get("title_native", ""),
                "synopsis":     meta.get("synopsis", "N/A"),
                "status":       meta.get("status", "N/A"),
                "chapters":     meta.get("chapters", "Ongoing"),
                "volumes":      meta.get("volumes", "N/A"),
                "type":         meta.get("type", "MANHWA"),
                "published":    meta.get("published", "N/A"),
            })
            r = meta.get("rating", 0)
            base["rating"] = f"{r}%" if isinstance(r, int) else str(r)

        return base

    def _substitute(self, template: str, tokens: Dict) -> str:
        result = template
        for key, value in tokens.items():
            result = result.replace("{" + key + "}", str(value) if value is not None else "N/A")
        # Clean up any un-filled tokens
        result = re.sub(r"\{[^}]+\}", "", result)
        # Collapse triple+ newlines into double
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()

    def _make_hashtags(self, title: str, category: str, genres: str) -> str:
        tags = []
        clean = re.sub(r"[^\w\s]", "", title)
        title_tag = "#" + "_".join(clean.split()).title()
        tags.append(title_tag)
        cat_map = {
            "movie":  "#Movie",
            "tvshow": "#TVShow",
            "anime":  "#Anime",
            "manhwa": "#Manhwa",
        }
        tags.append(cat_map.get(category, ""))
        for g in (genres or "").split(",")[:3]:
            g = g.strip()
            if g:
                tags.append("#" + g.replace(" ", ""))
        return " ".join(filter(None, tags))

    def validate_template(self, template: str, category: str) -> bool:
        return "{title}" in template

    def get_token_list(self, category: str) -> str:
        return "  ".join(self.TOKEN_DOCS.get(category, []))
