from handlers.base import BaseHandler
from fetchers.tmdb import TMDbFetcher


class TVShowHandler(BaseHandler):
    CATEGORY = "tvshow"
    PREFIX   = "tv"

    def __init__(self):
        super().__init__()
        self.fetcher = TMDbFetcher()

    async def _fetch_search(self, query):
        return await self.fetcher.search_tv(query)

    async def _fetch_detail(self, item_id):
        return await self.fetcher.get_tv(item_id)
