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
import random
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

    # Token bucket parameters
    _tokens = RATE_LIMIT  # Start with a full bucket
    _last_refill_time = time.time()
    _token_rate = RATE_LIMIT / RATE_PERIOD  # Tokens per second
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
        Implements token bucket algorithm for rate limiting to ensure we don't exceed 
        RATE_LIMIT requests per RATE_PERIOD.
        This method will wait if necessary to comply with the rate limit.
        """
        async with self._rate_limit_lock:
            current_time = time.time()

            # Calculate time elapsed since last token refill
            time_elapsed = current_time - self._last_refill_time

            # Calculate how many tokens to add based on elapsed time and token rate
            tokens_to_add = time_elapsed * self._token_rate

            if tokens_to_add > 0:
                # Add tokens to the bucket (up to the maximum capacity)
                self.__class__._tokens = min(self.__class__._tokens + tokens_to_add, self.RATE_LIMIT)
                # Update last refill time
                self.__class__._last_refill_time = current_time

            # If there are no tokens available, calculate wait time and sleep
            if self.__class__._tokens < 1:
                # Calculate how long to wait for at least one token
                wait_time = (1 - self.__class__._tokens) / self._token_rate
                logger.debug(f"Rate limit reached. Waiting {wait_time:.2f} seconds for a token.")
                await asyncio.sleep(wait_time)

                # After waiting, we should have at least one token
                self.__class__._tokens = 1
                self.__class__._last_refill_time = time.time()

            # Consume a token
            self.__class__._tokens -= 1

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

        # Initial backoff time in seconds
        base_backoff = 1
        max_backoff = 60  # Maximum backoff time in seconds

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
            except (aiohttp.ClientError, asyncio.TimeoutError, RateLimitError, APIError) as e:
                # Calculate exponential backoff with jitter
                # Exponential backoff: 2^attempt * base_backoff
                backoff = min(max_backoff, (2 ** (attempt - 1)) * base_backoff)
                # Add jitter: random value between 0 and backoff/2
                jitter = random.uniform(0, backoff / 2)
                # Total wait time with jitter
                wait_time = backoff + jitter

                error_type = e.__class__.__name__
                logger.warning(
                    f"{error_type} for {params['symbol']} (attempt {attempt}/{self.RETRIES}): {str(e)}. "
                    f"Retrying in {wait_time:.2f} seconds..."
                )

                if attempt == self.RETRIES:
                    logger.error(f"Failed to fetch data for {params['symbol']} after {self.RETRIES} attempts: {str(e)}")
                    raise DataDownloadError(f"Failed to fetch data for {params['symbol']} after {self.RETRIES} attempts: {str(e)}") from e

                await asyncio.sleep(wait_time)
                continue

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
        # Initial backoff time in seconds
        base_backoff = 1
        max_backoff = 60  # Maximum backoff time in seconds

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
            except (aiohttp.ClientError, asyncio.TimeoutError, PremiumEndpointError) as e:
                # Calculate exponential backoff with jitter
                # Exponential backoff: 2^attempt * base_backoff
                backoff = min(max_backoff, (2 ** (attempt - 1)) * base_backoff)
                # Add jitter: random value between 0 and backoff/2
                jitter = random.uniform(0, backoff / 2)
                # Total wait time with jitter
                wait_time = backoff + jitter

                error_type = e.__class__.__name__
                logger.warning(
                    f"{error_type} while fetching symbols (attempt {attempt}/{self.RETRIES}): {str(e)}. "
                    f"Retrying in {wait_time:.2f} seconds..."
                )

                if attempt == self.RETRIES:
                    logger.error(f"Failed to fetch symbols after {self.RETRIES} attempts: {str(e)}")
                    raise DataDownloadError(f"Failed to fetch symbols after {self.RETRIES} attempts: {str(e)}") from e

                await asyncio.sleep(wait_time)
                continue

        # final fallback
        return []
