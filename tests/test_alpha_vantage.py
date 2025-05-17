import unittest
import sys
import os
import json
import asyncio
from unittest import mock
from io import StringIO

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import aiohttp
from data_manager.alpha_vantage import AsyncAlphaVantageDownloader
from data_manager.exceptions import (
    APIError, RateLimitError, PremiumEndpointError, 
    InvalidResponseError, DataDownloadError
)


class TestAsyncAlphaVantageDownloader(unittest.TestCase):
    """Test cases for the AsyncAlphaVantageDownloader class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock session
        self.mock_session = mock.MagicMock(spec=aiohttp.ClientSession)

        # Create the downloader with the mock session
        self.downloader = AsyncAlphaVantageDownloader(session=self.mock_session, verify_ssl=False)

        # Sample data for testing
        self.sample_time_series_data = {
            "Meta Data": {
                "1. Information": "Daily Time Series with Adjusted close and volume",
                "2. Symbol": "AAPL",
                "3. Last Refreshed": "2023-01-31",
                "4. Output Size": "Full size",
                "5. Time Zone": "US/Eastern"
            },
            "Time Series (Daily)": {
                "2023-01-31": {
                    "1. open": "142.7000",
                    "2. high": "144.3400",
                    "3. low": "142.2800",
                    "4. close": "144.2900",
                    "5. adjusted close": "144.2900",
                    "6. volume": "86903491",
                    "7. dividend amount": "0.0000",
                    "8. split coefficient": "1.0000"
                },
                "2023-01-30": {
                    "1. open": "143.1600",
                    "2. high": "143.3100",
                    "3. low": "142.0000",
                    "4. close": "143.0000",
                    "5. adjusted close": "143.0000",
                    "6. volume": "64015367",
                    "7. dividend amount": "0.0000",
                    "8. split coefficient": "1.0000"
                }
            }
        }

        self.sample_symbols_csv = """symbol,name,exchange,assetType,ipoDate,delistingDate,status
AAPL,Apple Inc,NASDAQ,Stock,1980-12-12,,Active
MSFT,Microsoft Corporation,NASDAQ,Stock,1986-03-13,,Active
GOOG,Alphabet Inc,NASDAQ,Stock,2004-08-19,,Active
"""

    @mock.patch('data_manager.alpha_vantage.AsyncAlphaVantageDownloader._acquire_rate_limit')
    async def test_download_success(self, mock_acquire_rate_limit):
        """Test successful data download."""
        # Mock the response
        mock_response = mock.MagicMock()
        mock_response.raise_for_status = mock.MagicMock()
        mock_response.json.return_value = self.sample_time_series_data

        # Mock the session's get method to return our mock response
        mock_context_manager = mock.MagicMock()
        mock_context_manager.__aenter__.return_value = mock_response
        self.mock_session.get.return_value = mock_context_manager

        # Call the download method
        result = await self.downloader.download("AAPL")

        # Verify the result
        self.assertEqual(result, self.sample_time_series_data)

        # Verify that the session's get method was called with the correct parameters
        self.mock_session.get.assert_called_once()
        call_args = self.mock_session.get.call_args[1]
        self.assertEqual(call_args['params']['function'], "TIME_SERIES_DAILY_ADJUSTED")
        self.assertEqual(call_args['params']['symbol'], "AAPL")

        # Verify that rate limiting was applied
        mock_acquire_rate_limit.assert_called_once()

    @mock.patch('data_manager.alpha_vantage.AsyncAlphaVantageDownloader._acquire_rate_limit')
    async def test_download_api_error(self, mock_acquire_rate_limit):
        """Test handling of API errors."""
        # Mock the response with an error message
        mock_response = mock.MagicMock()
        mock_response.raise_for_status = mock.MagicMock()
        mock_response.json.return_value = {
            "Error Message": "Invalid API call. Please retry or visit the documentation."
        }

        # Mock the session's get method to return our mock response
        mock_context_manager = mock.MagicMock()
        mock_context_manager.__aenter__.return_value = mock_response
        self.mock_session.get.return_value = mock_context_manager

        # Call the download method and expect an APIError
        with self.assertRaises(APIError):
            await self.downloader.download("INVALID")

        # Verify that rate limiting was applied
        mock_acquire_rate_limit.assert_called_once()

    @mock.patch('data_manager.alpha_vantage.AsyncAlphaVantageDownloader._acquire_rate_limit')
    async def test_download_premium_endpoint_error(self, mock_acquire_rate_limit):
        """Test handling of premium endpoint errors."""
        # Mock the response with a premium endpoint message
        mock_response = mock.MagicMock()
        mock_response.raise_for_status = mock.MagicMock()
        mock_response.json.return_value = {
            "Information": "This is a premium endpoint. Please subscribe to a premium plan."
        }

        # Mock the session's get method to return our mock response
        mock_context_manager = mock.MagicMock()
        mock_context_manager.__aenter__.return_value = mock_response
        self.mock_session.get.return_value = mock_context_manager

        # Call the download method and expect a PremiumEndpointError
        with self.assertRaises(PremiumEndpointError):
            await self.downloader.download("AAPL", function="PREMIUM_FUNCTION")

        # Verify that rate limiting was applied
        mock_acquire_rate_limit.assert_called_once()

    @mock.patch('data_manager.alpha_vantage.AsyncAlphaVantageDownloader._acquire_rate_limit')
    async def test_download_rate_limit_error(self, mock_acquire_rate_limit):
        """Test handling of rate limit errors."""
        # Mock the response with an empty response (rate limiting)
        mock_response = mock.MagicMock()
        mock_response.raise_for_status = mock.MagicMock()
        mock_response.json.return_value = {}

        # Mock the session's get method to return our mock response
        mock_context_manager = mock.MagicMock()
        mock_context_manager.__aenter__.return_value = mock_response
        self.mock_session.get.return_value = mock_context_manager

        # Mock the retry behavior to avoid actual sleep
        with mock.patch('asyncio.sleep', return_value=None):
            # Call the download method and expect a DataDownloadError after retries
            with self.assertRaises(DataDownloadError):
                await self.downloader.download("AAPL")

        # Verify that rate limiting was applied
        self.assertEqual(mock_acquire_rate_limit.call_count, self.downloader.RETRIES)

    @mock.patch('data_manager.alpha_vantage.AsyncAlphaVantageDownloader._acquire_rate_limit')
    async def test_get_symbols_success(self, mock_acquire_rate_limit):
        """Test successful symbols retrieval."""
        # Mock the response
        mock_response = mock.MagicMock()
        mock_response.raise_for_status = mock.MagicMock()
        mock_response.text.return_value = self.sample_symbols_csv

        # Mock the session's get method to return our mock response
        mock_context_manager = mock.MagicMock()
        mock_context_manager.__aenter__.return_value = mock_response
        self.mock_session.get.return_value = mock_context_manager

        # Call the get_symbols method
        result = await self.downloader.get_symbols()

        # Verify the result
        self.assertEqual(result, ["AAPL", "MSFT", "GOOG"])

        # Verify that the session's get method was called with the correct parameters
        self.mock_session.get.assert_called_once()
        call_args = self.mock_session.get.call_args[1]
        self.assertEqual(call_args['params']['function'], "LISTING_STATUS")

        # Verify that rate limiting was applied
        mock_acquire_rate_limit.assert_called_once()

    @mock.patch('data_manager.alpha_vantage.AsyncAlphaVantageDownloader._acquire_rate_limit')
    async def test_get_symbols_with_exchange_filter(self, mock_acquire_rate_limit):
        """Test symbols retrieval with exchange filter."""
        # Mock the response
        mock_response = mock.MagicMock()
        mock_response.raise_for_status = mock.MagicMock()
        mock_response.text.return_value = self.sample_symbols_csv

        # Mock the session's get method to return our mock response
        mock_context_manager = mock.MagicMock()
        mock_context_manager.__aenter__.return_value = mock_response
        self.mock_session.get.return_value = mock_context_manager

        # Call the get_symbols method with exchange filter
        result = await self.downloader.get_symbols(exchange="NASDAQ")

        # Verify the result (should be the same as without filter since our mock doesn't filter)
        self.assertEqual(result, ["AAPL", "MSFT", "GOOG"])

        # Verify that rate limiting was applied
        mock_acquire_rate_limit.assert_called_once()

    @mock.patch('time.time')
    async def test_rate_limiting(self, mock_time):
        """Test the rate limiting mechanism."""
        # Reset the class-level rate limiter state
        AsyncAlphaVantageDownloader._request_timestamps = []

        # Mock time.time() to return controlled values
        mock_time.return_value = 1000.0

        # First call should add a timestamp without waiting
        await self.downloader._acquire_rate_limit()
        self.assertEqual(len(AsyncAlphaVantageDownloader._request_timestamps), 1)

        # Fill up to the rate limit
        for i in range(1, self.downloader.RATE_LIMIT):
            mock_time.return_value = 1000.0 + i
            await self.downloader._acquire_rate_limit()

        self.assertEqual(len(AsyncAlphaVantageDownloader._request_timestamps), self.downloader.RATE_LIMIT)

        # Next call should trigger waiting
        with mock.patch('asyncio.sleep') as mock_sleep:
            mock_time.return_value = 1000.0 + self.downloader.RATE_LIMIT
            await self.downloader._acquire_rate_limit()

            # Should wait for the oldest timestamp to expire
            expected_wait_time = (AsyncAlphaVantageDownloader._request_timestamps[0] + 
                                 self.downloader.RATE_PERIOD - 
                                 (1000.0 + self.downloader.RATE_LIMIT))
            mock_sleep.assert_called_once_with(expected_wait_time)


class AsyncioTestCase(unittest.TestCase):
    """Base class for asyncio test cases."""

    def run_async(self, coro):
        """Run a coroutine in the event loop."""
        return asyncio.run(coro)


# Modify the TestAsyncAlphaVantageDownloader class to use AsyncioTestCase
TestAsyncAlphaVantageDownloader.__bases__ = (AsyncioTestCase,)


# Wrap async test methods to run them with run_async
for name in dir(TestAsyncAlphaVantageDownloader):
    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestAsyncAlphaVantageDownloader, name)):
        method = getattr(TestAsyncAlphaVantageDownloader, name)

        def wrapper(self, method=method):
            return self.run_async(method(self))

        setattr(TestAsyncAlphaVantageDownloader, name, wrapper)


if __name__ == '__main__':
    unittest.main()
