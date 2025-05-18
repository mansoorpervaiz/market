import unittest
import sys
import os
import json
import asyncio
import pandas as pd
from unittest import mock
from pathlib import Path
from io import StringIO

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import aiohttp
from ingesters.DailyDataIngester import process_symbol, main
from data_manager.alpha_vantage import AsyncAlphaVantageDownloader
from data_manager.symbol_manager import SymbolManager
from config import config


class TestDailyDataIngester(unittest.TestCase):
    """Test cases for the DailyDataIngester module."""

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

        # Create a temporary directory for test files
        self.temp_dir = mock.MagicMock()
        self.temp_dir.name = "/tmp/test_daily_data"
        
        # Mock config paths
        self.original_data_json_location = config.DATA_JSON_LOCATION
        self.original_data_pickle_location = config.DATA_PICKLE_LOCATION
        config.DATA_JSON_LOCATION = os.path.join(self.temp_dir.name, "json")
        config.DATA_PICKLE_LOCATION = os.path.join(self.temp_dir.name, "pickle")

    def tearDown(self):
        """Tear down test fixtures."""
        # Restore original config paths
        config.DATA_JSON_LOCATION = self.original_data_json_location
        config.DATA_PICKLE_LOCATION = self.original_data_pickle_location

    @mock.patch('os.makedirs')
    @mock.patch('builtins.open', new_callable=mock.mock_open)
    @mock.patch('pandas.DataFrame.from_dict')
    @mock.patch('pandas.DataFrame.to_pickle')
    async def test_process_symbol_success(self, mock_to_pickle, mock_from_dict, mock_open, mock_makedirs):
        """Test successful processing of a symbol."""
        # Mock the DataFrame creation
        mock_df = mock.MagicMock()
        mock_from_dict.return_value = mock_df

        # Create a mock downloader that returns our sample data
        mock_downloader = mock.MagicMock()
        mock_downloader.download = mock.AsyncMock(return_value=self.sample_time_series_data)

        # Create a mock semaphore
        mock_sem = mock.MagicMock()
        mock_sem.__aenter__ = mock.AsyncMock(return_value=None)
        mock_sem.__aexit__ = mock.AsyncMock(return_value=None)

        # Create a list to track not found symbols
        not_found = []

        # Call the process_symbol function
        await process_symbol("AAPL", mock_downloader, not_found, mock_sem)

        # Verify that the downloader was called with the correct symbol
        mock_downloader.download.assert_called_once_with("AAPL")

        # Verify that the JSON file was opened and written
        mock_open.assert_called_with(os.path.join(config.DATA_JSON_LOCATION, "AAPL.json"), "w")
        mock_open().write.assert_called_once()

        # Verify that the DataFrame was created and saved as pickle
        mock_from_dict.assert_called_once_with(self.sample_time_series_data["Time Series (Daily)"], orient="index")
        mock_to_pickle.assert_called_once_with(os.path.join(config.DATA_PICKLE_LOCATION, "AAPL.pkl.gz"), compression="gzip")

        # Verify that the symbol was not added to the not_found list
        self.assertEqual(not_found, [])

    @mock.patch('os.makedirs')
    @mock.patch('builtins.open', new_callable=mock.mock_open)
    async def test_process_symbol_no_time_series(self, mock_open, mock_makedirs):
        """Test processing a symbol with no time series data."""
        # Create sample data with no time series
        data_no_time_series = {
            "Meta Data": {
                "1. Information": "Daily Time Series with Adjusted close and volume",
                "2. Symbol": "INVALID",
                "3. Last Refreshed": "2023-01-31",
                "4. Output Size": "Full size",
                "5. Time Zone": "US/Eastern"
            }
        }

        # Create a mock downloader that returns data with no time series
        mock_downloader = mock.MagicMock()
        mock_downloader.download = mock.AsyncMock(return_value=data_no_time_series)

        # Create a mock semaphore
        mock_sem = mock.MagicMock()
        mock_sem.__aenter__ = mock.AsyncMock(return_value=None)
        mock_sem.__aexit__ = mock.AsyncMock(return_value=None)

        # Create a list to track not found symbols
        not_found = []

        # Call the process_symbol function
        await process_symbol("INVALID", mock_downloader, not_found, mock_sem)

        # Verify that the downloader was called with the correct symbol
        mock_downloader.download.assert_called_once_with("INVALID")

        # Verify that the JSON file was opened and written
        mock_open.assert_called_with(os.path.join(config.DATA_JSON_LOCATION, "INVALID.json"), "w")
        mock_open().write.assert_called_once()

        # Verify that the symbol was added to the not_found list
        self.assertEqual(not_found, ["INVALID"])

    @mock.patch('os.makedirs')
    @mock.patch('os.path.exists')
    @mock.patch('builtins.open', new_callable=mock.mock_open)
    @mock.patch('asyncio.gather')
    @mock.patch('ingesters.DailyDataIngester.process_symbol')
    @mock.patch('data_manager.symbol_manager.SymbolManager')
    async def test_main_function(self, mock_symbol_manager_class, mock_process_symbol, 
                                mock_gather, mock_open, mock_exists, mock_makedirs):
        """Test the main function of the DailyDataIngester."""
        # Mock os.path.exists to return True for missing_symbols.txt
        mock_exists.return_value = True

        # Mock open to return a file with missing symbols
        mock_open.return_value.__enter__.return_value.readlines.return_value = ["MISSING1\n", "MISSING2\n"]

        # Mock SymbolManager
        mock_symbol_manager = mock.MagicMock()
        mock_symbol_manager.get_symbols_space_separated.return_value = ["AAPL", "MSFT", "GOOG"]
        mock_symbol_manager.save_symbols_to_file.return_value = "symbols.txt"
        mock_symbol_manager_class.return_value = mock_symbol_manager

        # Mock process_symbol to track calls
        mock_process_symbol.return_value = None

        # Mock gather to return None
        mock_gather.return_value = None

        # Call the main function
        await main()

        # Verify that directories were created
        self.assertEqual(mock_makedirs.call_count, 3)  # daily_dir, json_dir, pickle_dir

        # Verify that SymbolManager was initialized and used
        mock_symbol_manager.load_russell_1000_symbols.assert_called_once()
        mock_symbol_manager.get_symbols_space_separated.assert_called_once()
        mock_symbol_manager.save_symbols_to_file.assert_called_once_with("symbols.txt")

        # Verify that process_symbol was called for each symbol
        # 3 regular symbols + 2 missing symbols = 5 calls
        self.assertEqual(mock_process_symbol.call_count, 5)

        # Verify that gather was called once
        mock_gather.assert_called_once()

        # Verify that the missing symbols file was written
        mock_open.assert_called_with(mock.ANY, "w")


class AsyncioTestCase(unittest.TestCase):
    """Base class for asyncio test cases."""

    def run_async(self, coro):
        """Run a coroutine in the event loop."""
        return asyncio.run(coro)


# Modify the TestDailyDataIngester class to use AsyncioTestCase
TestDailyDataIngester.__bases__ = (AsyncioTestCase,)


# Wrap async test methods to run them with run_async
for name in dir(TestDailyDataIngester):
    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestDailyDataIngester, name)):
        method = getattr(TestDailyDataIngester, name)

        def wrapper(self, method=method):
            return self.run_async(method(self))

        setattr(TestDailyDataIngester, name, wrapper)


if __name__ == '__main__':
    unittest.main()