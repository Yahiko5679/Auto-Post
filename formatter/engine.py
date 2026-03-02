"""
Format Template Engine
Renders metadata dicts into caption strings using token substitution.
"""
import re
import logging
from typing import Dict, Optional
import config as cfg

logger = logging.getLogger(__name__)


class FormatEngine:
    _DEFAULTS = {
        "movie":  lambda: cfg.DEFAULT_MOVIE_FORMAT,
        "tvshow": lambda: cfg.DEFAULT_TV_FORMAT,
        "anime":  lambda: cfg.DEFAULT_ANIME_FORMAT,
        "manhwa": lambda: cfg.DEFAULT_MANHWA_FORMAT,
    }

    TOKEN_DOCS = {
        "movie":  ["{title}", "{year}", "{release_date}", "{runtime}", "{language}",
                   "{rating}", "{imdb_rating}", "{imdb_votes}", "{imdb_url}",
                   "{content_rating}", "{box_office}", "{awards}", "{metacritic}",
                   "{genres}", "{overview}", "{tagline}", "{audio}", "{quality}", "{hashtags}"],
        "tvshow": ["{title}", "{year}", "{release_date}", "{language}",
                   "{rating}", "{imdb_rating}", "{imdb_votes}", "{imdb_url}",
                   "{content_rating}", "{awards}", "{metacritic}",
                   "{genres}", "{overview}", "{status}", "{seasons}", "{episodes}",
                   "{network}", "{audio}", "{quality}", "{hashtags}"],
        "anime":  ["{title}", "{title_jp}", "{year}", "{rating}", "{genres}",
                   "{synopsis}", "{status}", "{episodes}", "{type}",
                   "{aired}", "{studio}", "{source}", "{season}", "{hashtags}"],
        "manhwa": ["{title}", "{title_native}", "{year}", "{rating}", "{genres}",
                   "{synopsis}", "{status}", "{chapters}", "{volumes}",
                   "{type}", "{published}", "{hashtags}"],
    }

    def render(
        self,
        category: str,
        metadata: Dict,
        template: Optional[str] = None,
        user_settings: Optional[Dict] = None,
    ) -> str:
        tpl    = template or self._DEFAULTS.get(category, lambda: "{title}")()
        tokens = self._tokens(category, metadata, user_settings or {})
        return self._sub(tpl, tokens)

    def _tokens(self, category: str, meta: Dict, s: Dict) -> Dict:
        quality = s.get("quality") or cfg.DEFAULT_QUALITY
        audio   = s.get("audio")   or cfg.DEFAULT_AUDIO
        title   = meta.get("title", "Unknown")
        genres  = meta.get("genres", "") or ""

        imdb_r   = meta.get("imdb_rating")
        imdb_str = str(imdb_r) if imdb_r and str(imdb_r) not in ("N/A", "0", "") else str(meta.get("rating", "N/A"))

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
            "genres":         genres,
            "quality":        quality,
            "audio":          audio,
            "hashtags":       self._hashtags(title, category, genres),
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
            r = meta.get("rating", 0)
            base.update({
                "rating":    f"{r}%" if isinstance(r, (int, float)) and r > 0 else "N/A",
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
        elif category == "manhwa":
            r = meta.get("rating", 0)
            base.update({
                "rating":       f"{r}%" if isinstance(r, (int, float)) and r > 0 else "N/A",
                "title_native": meta.get("title_native", ""),
                "synopsis":     meta.get("synopsis", "N/A"),
                "status":       meta.get("status", "N/A"),
                "chapters":     meta.get("chapters", "Ongoing"),
                "volumes":      meta.get("volumes", "N/A"),
                "type":         meta.get("type", "MANHWA"),
                "published":    meta.get("published", "N/A"),
            })

        return base

    def _sub(self, tpl: str, tokens: Dict) -> str:
        for k, v in tokens.items():
            tpl = tpl.replace("{" + k + "}", str(v) if v is not None else "")
        # Remove leftover unknown tokens
        tpl = re.sub(r"\{[^}]+\}", "", tpl)
        # Remove lines where the only content after label is N/A or empty
        lines   = tpl.split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            # Drop lines ending with » N/A  or  » ?  or  :  N/A
            if re.search(r"[»:]\s*(N/A|\?)\s*$", stripped):
                continue
            cleaned.append(line)
        result = "\n".join(cleaned)
        # Collapse 3+ blank lines to max 2
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()

    def _hashtags(self, title: str, category: str, genres: str) -> str:
        clean     = re.sub(r"[^\w\s]", "", title)
        tag       = "#" + "_".join(clean.split()).title()
        cat_tag   = {"movie": "#Movie", "tvshow": "#TVShow",
                     "anime": "#Anime", "manhwa": "#Manhwa"}.get(category, "")
        genre_tags = [
            "#" + g.strip().replace(" ", "")
            for g in (genres or "").split(",")[:3] if g.strip()
        ]
        return " ".join(filter(None, [tag, cat_tag] + genre_tags))

    def validate(self, template: str) -> bool:
        return "{title}" in template

    def token_list(self, category: str) -> str:
        return "  ".join(self.TOKEN_DOCS.get(category, []))
