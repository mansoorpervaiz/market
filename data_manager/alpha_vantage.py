import aiohttp
import asyncio

class AsyncAlphaVantageDownloader:
    BASE_URL = "https://www.alphavantage.co/query"
    API_KEY = "C09R44C5Y37M2C8W"     # replace with your key
    RETRIES = 3

    def __init__(self, session: aiohttp.ClientSession = None):
        self._own_session = session is None
        self.session = session

    async def download(self, symbol: str) -> dict:
        if self._own_session:
            # create a short‑lived session if caller didn't supply one
            async with aiohttp.ClientSession() as sess:
                return await self._fetch_with_retries(sess, symbol)
        else:
            return await self._fetch_with_retries(self.session, symbol)

    async def _fetch_with_retries(self, session: aiohttp.ClientSession, symbol: str) -> dict:
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "full", # "other option is compact"
            "apikey": self.API_KEY,
        }
        backoff = 1
        for attempt in range(1, self.RETRIES + 1):
            try:
                async with session.get(self.BASE_URL, params=params) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    # check for valid payload
                    if "Time Series (Daily)" in data:
                        return data
                    # AlphaVantage will return a note or empty if rate‑limited
                # fell through → retry
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == self.RETRIES:
                    raise
            await asyncio.sleep(backoff)
            backoff *= 2
        # final fallback
        return {}
