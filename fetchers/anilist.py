"""
AniList GraphQL Fetcher — Manhwa / Manga
"""

import aiohttp
import logging
from typing import Optional, List, Dict
from config import ANILIST_URL, MAX_SEARCH_RESULTS

logger = logging.getLogger(__name__)

SEARCH_QUERY = """
query ($search: String, $type: MediaType, $format: MediaFormat) {
  Page(perPage: 5) {
    media(search: $search, type: $type, format: $format, sort: POPULARITY_DESC) {
      id
      title { romaji english native }
      coverImage { extraLarge }
      averageScore
      status
      genres
      chapters
      volumes
      startDate { year month day }
      format
      countryOfOrigin
    }
  }
}
"""

DETAIL_QUERY = """
query ($id: Int) {
  Media(id: $id, type: MANGA) {
    id
    title { romaji english native }
    coverImage { extraLarge }
    bannerImage
    averageScore
    meanScore
    status
    genres
    tags { name }
    chapters
    volumes
    startDate { year month day }
    endDate { year month day }
    description(asHtml: false)
    format
    countryOfOrigin
    siteUrl
    staff(perPage: 5) { edges { role node { name { full } } } }
  }
}
"""


class AniListFetcher:
    async def _gql(self, query: str, variables: Dict) -> Optional[Dict]:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    ANILIST_URL,
                    json={"query": query, "variables": variables},
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=12),
                ) as r:
                    if r.status == 200:
                        return await r.json()
        except Exception as e:
            logger.error(f"AniList request failed: {e}")
        return None

    async def search_manhwa(self, query: str) -> List[Dict]:
        # Try MANHWA format first, fallback to all MANGA
        variables = {"search": query, "type": "MANGA", "format": "MANHWA"}
        data = await self._gql(SEARCH_QUERY, variables)
        results = (data or {}).get("data", {}).get("Page", {}).get("media", [])

        if not results:
            variables = {"search": query, "type": "MANGA"}
            data = await self._gql(SEARCH_QUERY, variables)
            results = (data or {}).get("data", {}).get("Page", {}).get("media", [])

        return [self._slim(r) for r in results[:MAX_SEARCH_RESULTS]]

    async def get_manhwa(self, anilist_id: int) -> Optional[Dict]:
        data = await self._gql(DETAIL_QUERY, {"id": anilist_id})
        media = (data or {}).get("data", {}).get("Media")
        if not media:
            return None
        return self._full(media)

    def _slim(self, r: Dict) -> Dict:
        title = r.get("title", {})
        return {
            "id": r.get("id"),
            "title": title.get("english") or title.get("romaji", "Unknown"),
            "year": str(r.get("startDate", {}).get("year") or ""),
            "poster": (r.get("coverImage") or {}).get("extraLarge"),
            "rating": r.get("averageScore") or 0,
            "format": r.get("format", "MANHWA"),
            "country": r.get("countryOfOrigin", "KR"),
        }

    def _full(self, r: Dict) -> Dict:
        title = r.get("title", {})
        sd = r.get("startDate", {})
        ed = r.get("endDate", {})
        published = f"{sd.get('year', '?')}" if sd.get("year") else "N/A"
        ended = f"{ed.get('year', '')}" if ed.get("year") else ""
        pub_str = f"{published}–{ended}" if ended else published

        genres = ", ".join(r.get("genres", [])) or "N/A"
        description = r.get("description", "") or "No synopsis available."
        # Clean AniList HTML-ish descriptions
        import re
        description = re.sub(r"<[^>]+>", "", description).strip()
        description = re.sub(r"\n{3,}", "\n\n", description)

        fmt = r.get("format", "MANHWA")
        country_map = {"KR": "MANHWA", "JP": "MANGA", "CN": "MANHUA"}
        media_type = country_map.get(r.get("countryOfOrigin", "KR"), fmt)

        return {
            "id": r.get("id"),
            "title": title.get("english") or title.get("romaji", "Unknown"),
            "title_native": title.get("native", ""),
            "year": str(sd.get("year") or ""),
            "poster": (r.get("coverImage") or {}).get("extraLarge"),
            "banner": r.get("bannerImage"),
            "rating": r.get("averageScore") or 0,
            "genres": genres,
            "synopsis": description,
            "status": (r.get("status") or "").replace("_", " ").title(),
            "chapters": r.get("chapters") or "Ongoing",
            "volumes": r.get("volumes") or "N/A",
            "published": pub_str,
            "type": media_type,
            "site_url": r.get("siteUrl", ""),
            "category": "manhwa",
        }
