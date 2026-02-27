from handlers.base import BaseHandler
from fetchers.tmdb import TMDbFetcher


class MovieHandler(BaseHandler):
    CATEGORY = "movie"
    PREFIX   = "movie"

    def __init__(self):
        super().__init__()
        self.fetcher = TMDbFetcher()

    async def _fetch_search(self, query):
        return await self.fetcher.search_movies(query)

    async def _fetch_detail(self, item_id):
        return await self.fetcher.get_movie(item_id)
