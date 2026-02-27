from handlers.base import BaseHandler
from fetchers.anilist import AniListFetcher


class ManhwaHandler(BaseHandler):
    CATEGORY = "manhwa"
    PREFIX   = "manhwa"

    def __init__(self):
        super().__init__()
        self.fetcher = AniListFetcher()

    async def _fetch_search(self, query):
        return await self.fetcher.search_manhwa(query)

    async def _fetch_detail(self, item_id):
        return await self.fetcher.get_manhwa(item_id)
