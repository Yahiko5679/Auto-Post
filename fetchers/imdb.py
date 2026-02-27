"""
IMDb Fetcher
━━━━━━━━━━━━
Enriches TMDb data with real IMDb ratings, votes, awards, box office.
Uses two possible sources (tries in order):

1. RapidAPI IMDb API  — rich data, needs IMDB_API_KEY from RapidAPI
   https://rapidapi.com/apidojo/api/imdb8

2. OMDb API (fallback) — simpler, free tier (1000/day), needs OMDB_API_KEY
   https://www.omdbapi.com/

Both are optional. If neither key is set, IMDb enrichment is silently skipped
and TMDb's vote_average is used as the rating.
"""

import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any
import os

logger = logging.getLogger(__name__)

IMDB_RAPIDAPI_KEY  = os.getenv("IMDB_API_KEY", "")
OMDB_API_KEY       = os.getenv("OMDB_API_KEY", "")

RAPIDAPI_HOST      = "imdb8.p.rapidapi.com"
RAPIDAPI_BASE      = f"https://{RAPIDAPI_HOST}"
OMDB_BASE          = "https://www.omdbapi.com"


class IMDbFetcher:
    """
    Fetches IMDb-specific data:
      - IMDb rating & vote count
      - Box office gross
      - Awards summary
      - IMDb ID (tt-number)
      - Content rating (PG, R, etc.)
      - Metacritic score
    """

    def __init__(self):
        self._cache: Dict[str, Dict] = {}   # simple in-process cache

    # ── Public API ─────────────────────────────────────────────────────────────

    async def enrich(self, tmdb_meta: Dict) -> Dict:
        """
        Given a TMDb metadata dict, return an enriched copy with
        real IMDb data merged in. Never raises — returns original on failure.
        """
        imdb_id = tmdb_meta.get("imdb_id")      # some TMDb calls include this
        title   = tmdb_meta.get("title", "")
        year    = tmdb_meta.get("year", "")

        imdb_data = None

        # Try to fetch by IMDb ID first (most accurate)
        if imdb_id:
            imdb_data = await self._fetch_by_id(imdb_id)

        # Fallback: search by title + year
        if not imdb_data and title:
            imdb_data = await self._fetch_by_title(title, year)

        if not imdb_data:
            return tmdb_meta          # no enrichment available, return as-is

        return self._merge(tmdb_meta, imdb_data)

    async def get_imdb_id_for_tmdb(self, tmdb_id: int, media_type: str = "movie") -> Optional[str]:
        """
        Fetch IMDb tt-ID using TMDb's /find endpoint.
        Useful when the detail endpoint doesn't include imdb_id.
        """
        from config import TMDB_API_KEY, TMDB_BASE_URL
        url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}/external_ids"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    url,
                    params={"api_key": TMDB_API_KEY},
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        return data.get("imdb_id")
        except Exception as e:
            logger.debug(f"TMDb external_ids failed: {e}")
        return None

    # ── RapidAPI IMDb ──────────────────────────────────────────────────────────

    async def _rapidapi_get(self, endpoint: str, params: Dict) -> Optional[Dict]:
        if not IMDB_RAPIDAPI_KEY:
            return None
        headers = {
            "X-RapidAPI-Key":  IMDB_RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST,
        }
        url = f"{RAPIDAPI_BASE}{endpoint}"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    url, headers=headers, params=params,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as r:
                    if r.status == 200:
                        return await r.json()
                    logger.debug(f"RapidAPI IMDb {r.status}: {endpoint}")
        except Exception as e:
            logger.debug(f"RapidAPI IMDb error: {e}")
        return None

    async def _rapidapi_fetch_by_id(self, imdb_id: str) -> Optional[Dict]:
        """Fetch title overview from RapidAPI IMDb by tt-id."""
        data = await self._rapidapi_get(
            "/title/get-overview-details",
            {"tconst": imdb_id, "currentCountry": "US"},
        )
        if not data:
            return None
        return self._parse_rapidapi(data, imdb_id)

    async def _rapidapi_search(self, title: str, year: str) -> Optional[Dict]:
        """Search RapidAPI IMDb for a title."""
        data = await self._rapidapi_get(
            "/auto-complete",
            {"q": f"{title} {year}".strip()},
        )
        if not data:
            return None
        suggestions = data.get("d", [])
        for s in suggestions[:3]:
            if s.get("qid") in ("movie", "tvSeries", "tvMiniSeries"):
                imdb_id = s.get("id")
                if imdb_id:
                    return await self._rapidapi_fetch_by_id(imdb_id)
        return None

    def _parse_rapidapi(self, data: Dict, imdb_id: str) -> Dict:
        ratings = data.get("ratings", {})
        title_meta = data.get("title", {})
        box = data.get("boxOffice", {})
        return {
            "imdb_id":         imdb_id,
            "imdb_rating":     ratings.get("rating"),
            "imdb_votes":      _fmt_votes(ratings.get("ratingCount")),
            "imdb_url":        f"https://www.imdb.com/title/{imdb_id}/",
            "content_rating":  data.get("certificate", {}).get("certificate", "N/A"),
            "box_office":      box.get("openingWeekendGross", {}).get("amount") or
                               box.get("cumulativeWorldwideGross", {}).get("amount"),
            "awards":          _fmt_awards(data.get("awards", {})),
            "metacritic":      None,   # not in this endpoint
        }

    # ── OMDb (fallback) ────────────────────────────────────────────────────────

    async def _omdb_get(self, params: Dict) -> Optional[Dict]:
        if not OMDB_API_KEY:
            return None
        params["apikey"] = OMDB_API_KEY
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    OMDB_BASE, params=params,
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        if data.get("Response") == "True":
                            return data
        except Exception as e:
            logger.debug(f"OMDb error: {e}")
        return None

    async def _omdb_fetch_by_id(self, imdb_id: str) -> Optional[Dict]:
        data = await self._omdb_get({"i": imdb_id, "plot": "short"})
        return self._parse_omdb(data) if data else None

    async def _omdb_search(self, title: str, year: str) -> Optional[Dict]:
        params = {"t": title, "plot": "short"}
        if year:
            params["y"] = year
        data = await self._omdb_get(params)
        return self._parse_omdb(data) if data else None

    def _parse_omdb(self, data: Dict) -> Dict:
        imdb_id = data.get("imdbID", "")
        rating  = data.get("imdbRating")
        meta    = None
        for r in data.get("Ratings", []):
            if "Metacritic" in r.get("Source", ""):
                meta = r.get("Value", "").replace("/100", "")

        box = data.get("BoxOffice", "N/A")
        if box == "N/A":
            box = None

        return {
            "imdb_id":        imdb_id,
            "imdb_rating":    float(rating) if rating and rating != "N/A" else None,
            "imdb_votes":     data.get("imdbVotes", "N/A").replace(",", ""),
            "imdb_url":       f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None,
            "content_rating": data.get("Rated", "N/A"),
            "box_office":     box,
            "awards":         data.get("Awards", "N/A"),
            "metacritic":     meta,
        }

    # ── Unified fetch logic ────────────────────────────────────────────────────

    async def _fetch_by_id(self, imdb_id: str) -> Optional[Dict]:
        if imdb_id in self._cache:
            return self._cache[imdb_id]

        # Try RapidAPI first, then OMDb
        result = await self._rapidapi_fetch_by_id(imdb_id)
        if not result:
            result = await self._omdb_fetch_by_id(imdb_id)

        if result:
            self._cache[imdb_id] = result
        return result

    async def _fetch_by_title(self, title: str, year: str) -> Optional[Dict]:
        # Try RapidAPI first, then OMDb
        result = await self._rapidapi_search(title, year)
        if not result:
            result = await self._omdb_search(title, year)
        return result

    # ── Merge IMDb data into TMDb metadata ────────────────────────────────────

    def _merge(self, tmdb: Dict, imdb: Dict) -> Dict:
        merged = dict(tmdb)

        # Use IMDb rating if available (more trusted than TMDb vote_average)
        imdb_rating = imdb.get("imdb_rating")
        if imdb_rating:
            merged["rating"]      = imdb_rating
            merged["rating_src"]  = "IMDb"
        else:
            merged["rating_src"]  = "TMDb"

        # Add IMDb-exclusive fields
        merged["imdb_id"]        = imdb.get("imdb_id", tmdb.get("imdb_id", ""))
        merged["imdb_votes"]     = imdb.get("imdb_votes", "N/A")
        merged["imdb_url"]       = imdb.get("imdb_url", "")
        merged["content_rating"] = imdb.get("content_rating", "N/A")
        merged["box_office"]     = _fmt_box_office(imdb.get("box_office"))
        merged["awards"]         = imdb.get("awards", "N/A")
        merged["metacritic"]     = imdb.get("metacritic", "N/A")

        return merged


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt_votes(count) -> str:
    if count is None:
        return "N/A"
    try:
        n = int(count)
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.0f}K"
        return str(n)
    except Exception:
        return str(count)


def _fmt_box_office(value) -> str:
    if not value:
        return "N/A"
    try:
        n = int(str(value).replace(",", "").replace("$", ""))
        if n >= 1_000_000_000:
            return f"${n/1_000_000_000:.2f}B"
        if n >= 1_000_000:
            return f"${n/1_000_000:.1f}M"
        return f"${n:,}"
    except Exception:
        return str(value)


def _fmt_awards(awards_data: Dict) -> str:
    if not awards_data or not isinstance(awards_data, dict):
        return "N/A"
    wins      = awards_data.get("wins", 0)
    noms      = awards_data.get("nominations", 0)
    highlight = awards_data.get("highlight", {}).get("text", "")
    if highlight:
        return highlight
    if wins or noms:
        return f"{wins} wins, {noms} nominations"
    return "N/A"
