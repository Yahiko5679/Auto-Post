"""
Jikan v4 Fetcher — Anime (MyAnimeList data, no API key needed)
"""

import aiohttp
import asyncio
import logging
from typing import Optional, List, Dict
from config import JIKAN_BASE_URL, MAX_SEARCH_RESULTS

logger = logging.getLogger(__name__)


class JikanFetcher:
    async def _get(self, endpoint: str, params: Dict = {}) -> Optional[Dict]:
        url = f"{JIKAN_BASE_URL}{endpoint}"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, params=params, timeout=aiohttp.ClientTimeout(total=12)) as r:
                    if r.status == 200:
                        return await r.json()
                    elif r.status == 429:
                        # Rate limit — wait and retry once
                        await asyncio.sleep(2)
                        async with s.get(url, params=params, timeout=aiohttp.ClientTimeout(total=12)) as r2:
                            if r2.status == 200:
                                return await r2.json()
        except Exception as e:
            logger.error(f"Jikan request failed: {e}")
        return None

    async def search_anime(self, query: str) -> List[Dict]:
        data = await self._get("/anime", {"q": query, "limit": MAX_SEARCH_RESULTS, "sfw": False})
        if not data:
            return []
        return [self._slim(r) for r in data.get("data", [])]

    async def get_anime(self, mal_id: int) -> Optional[Dict]:
        data = await self._get(f"/anime/{mal_id}/full")
        if not data:
            return None
        return self._full(data.get("data", {}))

    def _slim(self, r: Dict) -> Dict:
        score = r.get("score") or 0
        return {
            "id": r.get("mal_id"),
            "title": r.get("title_english") or r.get("title", "Unknown"),
            "year": str(r.get("year") or ""),
            "poster": (r.get("images") or {}).get("jpg", {}).get("large_image_url"),
            "rating": round(score * 10),
        }

    def _full(self, r: Dict) -> Dict:
        genres = ", ".join(g["name"] for g in r.get("genres", []))
        themes = ", ".join(t["name"] for t in r.get("themes", []))
        all_genres = ", ".join(filter(None, [genres, themes])) or "N/A"
        score = r.get("score") or 0
        aired = r.get("aired", {}).get("string", "N/A")
        return {
            "id": r.get("mal_id"),
            "title": r.get("title_english") or r.get("title", "Unknown"),
            "title_jp": r.get("title_japanese", ""),
            "year": str(r.get("year") or ""),
            "poster": (r.get("images") or {}).get("jpg", {}).get("large_image_url"),
            "rating": round(score * 10),
            "genres": all_genres,
            "synopsis": r.get("synopsis", "No synopsis available."),
            "status": r.get("status", "N/A"),
            "episodes": r.get("episodes") or "?",
            "type": r.get("type", "TV"),
            "aired": aired,
            "studio": ", ".join(s["name"] for s in r.get("studios", [])) or "N/A",
            "source": r.get("source", "N/A"),
            "duration": r.get("duration", "N/A"),
            "season": r.get("season", "").capitalize(),
            "category": "anime",
        }
