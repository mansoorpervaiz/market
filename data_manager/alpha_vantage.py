# Copyright (c) 2025 Mansoor Pervaiz
# All rights reserved.
#
# This file is part of a proprietary software project.
# Unauthorized copying, distribution, modification, or use of this file,
# via any medium, is strictly prohibited unless explicit permission is granted
# by the author.
#
# For licensing inquiries, contact: mansoorpervaizdev@gmail.com

import aiohttp
import asyncio
import csv
import json
import os
import ssl
import time
from io import StringIO

from config import config
from interfaces.data_access.downloader_interface import DownloaderInterface
from data_manager.exceptions import (
    APIError, RateLimitError, PremiumEndpointError, 
    InvalidResponseError, DataDownloadError
)
from logger import get_logger

# Initialize logger
logger = get_logger(__name__)

class AsyncAlphaVantageDownloader(DownloaderInterface):
    BASE_URL = config.ALPHA_VANTAGE_BASE_URL
    API_KEY = config.ALPHA_VANTAGE_API_KEY
    RETRIES = config.ALPHA_VANTAGE_RETRIES
    # Rate limiting
    RATE_LIMIT = config.ALPHA_VANTAGE_RATE_LIMIT
    RATE_PERIOD = config.ALPHA_VANTAGE_RATE_PERIOD  # seconds

    # Class-level rate limiter
    _rate_limit_semaphore = asyncio.Semaphore(RATE_LIMIT)
    _request_timestamps = []
    _rate_limit_lock = asyncio.Lock()

    def __init__(self, session: aiohttp.ClientSession = None, verify_ssl: bool = False):
        self._own_session = session is None
        self.session = session
        self.verify_ssl = verify_ssl

        # Create SSL context
        self.ssl_context = ssl.create_default_context()
        if not verify_ssl:
            # Disable SSL verification if requested
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE

    async def _acquire_rate_limit(self):
        """
        Implements rate limiting to ensure we don't exceed RATE_LIMIT requests per RATE_PERIOD.
        This method will wait if necessary to comply with the rate limit.
        """
        async with self._rate_limit_lock:
            current_time = time.time()

            # Remove timestamps older than RATE_PERIOD
            self._request_timestamps = [ts for ts in self._request_timestamps 
                                       if current_time - ts < self.RATE_PERIOD]

            # If we've reached the rate limit, wait until we can make another request
            if len(self._request_timestamps) >= self.RATE_LIMIT:
                # Calculate how long to wait
                oldest_timestamp = min(self._request_timestamps)
                wait_time = oldest_timestamp + self.RATE_PERIOD - current_time
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    # Update current time after waiting
                    current_time = time.time()
                    # Clean up timestamps again after waiting
                    self._request_timestamps = [ts for ts in self._request_timestamps 
                                              if current_time - ts < self.RATE_PERIOD]

            # Add current timestamp to the list
            self._request_timestamps.append(current_time)

            # Return the current time for reference
            return current_time

    async def download(self, symbol: str, function: str = "TIME_SERIES_DAILY_ADJUSTED", **kwargs) -> dict:
        if self._own_session:
            # create a short‑lived session if caller didn't supply one
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=self.ssl_context)) as sess:
                return await self._fetch_with_retries(sess, symbol, function, **kwargs)
        else:
            return await self._fetch_with_retries(self.session, symbol, function, **kwargs)

    async def _fetch_with_retries(self, session: aiohttp.ClientSession, symbol: str, function: str = "TIME_SERIES_DAILY_ADJUSTED", **kwargs) -> dict:
        params = {
            "function": function,
            "symbol": symbol,
            "outputsize": "full", # "other option is compact"
            "apikey": self.API_KEY,
        }
        # Add any additional parameters
        params.update(kwargs)
        backoff = 1
        for attempt in range(1, self.RETRIES + 1):
            try:
                # Apply rate limiting before making the request
                await self._acquire_rate_limit()

                async with session.get(self.BASE_URL, params=params) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

                    # Check for premium endpoint message
                    if 'Information' in data and 'premium' in data['Information'].lower():
                        error_msg = f"Premium endpoint error for {params['symbol']}: {data['Information']}"
                        logger.error(error_msg)
                        raise PremiumEndpointError(error_msg)
                    if 'Error Message' in data:
                        error_msg = f"Error for {params['symbol']}: {data['Error Message']}"
                        logger.error(error_msg)
                        raise APIError(error_msg)

                    # Check if response is empty
                    if not data:
                        # Empty response, likely due to rate limiting
                        logger.warning(f"Empty response for {params['symbol']}, likely due to rate limiting. Retrying...")
                        raise RateLimitError(f"Empty response for {params['symbol']}, likely due to rate limiting")
                    # check for valid payload based on function
                    elif function == "TIME_SERIES_DAILY_ADJUSTED" and "Time Series (Daily)" in data:
                        return data
                    elif function == "TIME_SERIES_INTRADAY":
                        # For intraday data, the key includes the interval
                        interval = kwargs.get('interval', '1min')
                        time_series_key = f"Time Series ({interval})"
                        if time_series_key in data:
                            return data
                    # AlphaVantage will return a note or empty if rate‑limited
                # fell through → retry
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"Network error for {params['symbol']} (attempt {attempt}/{self.RETRIES}): {str(e)}")
                if attempt == self.RETRIES:
                    logger.error(f"Failed to fetch data for {params['symbol']} after {self.RETRIES} attempts: {str(e)}")
                    raise DataDownloadError(f"Failed to fetch data for {params['symbol']} after {self.RETRIES} attempts: {str(e)}") from e
            await asyncio.sleep(backoff)
            backoff *= 2
        # final fallback
        return {}

    async def get_symbols(self, exchange: str = None) -> list:
        """
        Fetch a list of symbols from Alpha Vantage.

        Args:
            exchange: Optional filter for exchange (e.g., 'NYSE', 'NASDAQ')
                     If None, returns symbols from all exchanges

        Returns:
            List of stock symbols
        """
        params = {
            "function": "LISTING_STATUS",
            "apikey": self.API_KEY,
        }

        if self._own_session:
            # create a short‑lived session if caller didn't supply one
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=self.ssl_context)) as sess:
                return await self._fetch_symbols_with_retries(sess, params, exchange)
        else:
            return await self._fetch_symbols_with_retries(self.session, params, exchange)

    async def _fetch_symbols_with_retries(self, session: aiohttp.ClientSession, params: dict, exchange: str = None) -> list:
        backoff = 1
        for attempt in range(1, self.RETRIES + 1):
            try:
                # Apply rate limiting before making the request
                await self._acquire_rate_limit()

                async with session.get(self.BASE_URL, params=params) as resp:
                    resp.raise_for_status()
                    response_text = await resp.text()

                    # Check if response might be JSON (premium endpoint message)
                    if response_text.strip().startswith('{'):
                        try:
                            data = json.loads(response_text)
                            # Check for premium endpoint message
                            if 'Information' in data and 'premium' in data['Information'].lower():
                                error_msg = f"Premium endpoint error: {data['Information']}"
                                logger.error(error_msg)
                                raise PremiumEndpointError(error_msg)
                        except json.JSONDecodeError:
                            # Not valid JSON, continue with CSV parsing
                            pass

                    # Parse CSV data
                    reader = csv.DictReader(StringIO(response_text))
                    symbols = []

                    for row in reader:
                        # Filter by exchange if specified
                        if exchange is None or row.get('exchange') == exchange:
                            symbol = row.get('symbol')
                            if symbol and isinstance(symbol, str) and symbol.isalnum():
                                symbols.append(symbol)

                    return symbols
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"Network error while fetching symbols (attempt {attempt}/{self.RETRIES}): {str(e)}")
                if attempt == self.RETRIES:
                    logger.error(f"Failed to fetch symbols after {self.RETRIES} attempts: {str(e)}")
                    raise DataDownloadError(f"Failed to fetch symbols after {self.RETRIES} attempts: {str(e)}") from e
            await asyncio.sleep(backoff)
            backoff *= 2

        # final fallback
        return []
