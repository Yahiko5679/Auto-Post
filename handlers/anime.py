from handlers.base import BaseHandler
from fetchers.jikan import JikanFetcher


class AnimeHandler(BaseHandler):
    CATEGORY = "anime"
    PREFIX   = "anime"

    def __init__(self):
        super().__init__()
        self.fetcher = JikanFetcher()

    async def _fetch_search(self, query):
        return await self.fetcher.search_anime(query)

    async def _fetch_detail(self, item_id):
        return await self.fetcher.get_anime(item_id)
