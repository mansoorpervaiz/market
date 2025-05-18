import unittest
import sys
import os
import json
import asyncio
import pandas as pd
from unittest import mock
from pathlib import Path
from datetime import datetime
from io import StringIO

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import aiohttp
from ingesters.IntradayDataIngester import process_symbol, main, generate_month_list
from data_manager.alpha_vantage import AsyncAlphaVantageDownloader
from data_manager.symbol_manager import SymbolManager
from config import config


class TestIntradayDataIngester(unittest.TestCase):
    """Test cases for the IntradayDataIngester module."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock session
        self.mock_session = mock.MagicMock(spec=aiohttp.ClientSession)

        # Create the downloader with the mock session
        self.downloader = AsyncAlphaVantageDownloader(session=self.mock_session, verify_ssl=False)

        # Sample data for testing
        self.sample_time_series_data = {
            "Meta Data": {
                "1. Information": "Intraday (60min) open, high, low, close prices and volume",
                "2. Symbol": "AAPL",
                "3. Last Refreshed": "2023-01-31 16:00:00",
                "4. Interval": "60min",
                "5. Output Size": "Full size",
                "6. Time Zone": "US/Eastern"
            },
            "Time Series (60min)": {
                "2023-01-31 16:00:00": {
                    "1. open": "142.7000",
                    "2. high": "144.3400",
                    "3. low": "142.2800",
                    "4. close": "144.2900",
                    "5. volume": "8690349"
                },
                "2023-01-31 15:00:00": {
                    "1. open": "143.1600",
                    "2. high": "143.3100",
                    "3. low": "142.0000",
                    "4. close": "143.0000",
                    "5. volume": "6401536"
                }
            }
        }

        # Create a temporary directory for test files
        self.temp_dir = mock.MagicMock()
        self.temp_dir.name = "/tmp/test_intraday_data"
        
        # Mock config paths
        self.original_data_root_dir = config.DATA_ROOT_DIR
        config.DATA_ROOT_DIR = self.temp_dir.name

    def tearDown(self):
        """Tear down test fixtures."""
        # Restore original config paths
        config.DATA_ROOT_DIR = self.original_data_root_dir

    def test_generate_month_list(self):
        """Test the generate_month_list function."""
        # Test with a specific start year and month
        with mock.patch('ingesters.IntradayDataIngester.datetime') as mock_datetime:
            # Mock the current date to be 2023-03-15
            mock_now = mock.MagicMock()
            mock_now.year = 2023
            mock_now.month = 3
            mock_datetime.now.return_value = mock_now

            # Generate months from 2022-06 to 2023-03
            months = generate_month_list(2022, 6)

            # Expected months in reverse order (most recent first)
            expected_months = [
                "2023-03", "2023-02", "2023-01", 
                "2022-12", "2022-11", "2022-10", "2022-09", "2022-08", "2022-07", "2022-06"
            ]

            self.assertEqual(months, expected_months)

    def test_generate_month_list_current_year(self):
        """Test generate_month_list with the current year."""
        # Get the current year and month
        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month

        # Generate months from the beginning of the current year
        months = generate_month_list(current_year, 1)

        # Expected months in reverse order (most recent first)
        expected_months = []
        for month in range(current_month, 0, -1):
            expected_months.append(f"{current_year}-{month:02d}")

        self.assertEqual(months, expected_months)

    @mock.patch('os.makedirs')
    @mock.patch('builtins.open', new_callable=mock.mock_open)
    @mock.patch('pandas.DataFrame.from_dict')
    @mock.patch('pandas.DataFrame.to_pickle')
    async def test_process_symbol_success(self, mock_to_pickle, mock_from_dict, mock_open, mock_makedirs):
        """Test successful processing of a symbol with intraday data."""
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
        await process_symbol("AAPL", mock_downloader, not_found, mock_sem, interval="60min")

        # Verify that the downloader was called with the correct parameters
        # Note: We expect multiple calls for each month, but in our test we're mocking to return the same data
        mock_downloader.download.assert_called_with(
            "AAPL", 
            function="TIME_SERIES_INTRADAY", 
            interval="60min",
            month=mock.ANY,
            outputsize="full"
        )

        # Verify that the JSON file was opened and written
        json_dir = Path(config.DATA_ROOT_DIR) / "intraday" / "json" / "60min"
        mock_open.assert_called_with(json_dir / "AAPL.json", "w")
        mock_open().write.assert_called_once()

        # Verify that the DataFrame was created and saved as pickle
        mock_from_dict.assert_called_once_with(mock.ANY, orient="index")
        pickle_dir = Path(config.DATA_ROOT_DIR) / "intraday" / "pickle" / "60min"
        mock_to_pickle.assert_called_once_with(pickle_dir / "AAPL.pkl.gz", compression="gzip")

        # Verify that the symbol was not added to the not_found list
        self.assertEqual(not_found, [])

    @mock.patch('os.makedirs')
    @mock.patch('builtins.open', new_callable=mock.mock_open)
    async def test_process_symbol_no_data(self, mock_open, mock_makedirs):
        """Test processing a symbol with no intraday data."""
        # Create a mock downloader that returns empty data
        mock_downloader = mock.MagicMock()
        mock_downloader.download = mock.AsyncMock(return_value={})

        # Create a mock semaphore
        mock_sem = mock.MagicMock()
        mock_sem.__aenter__ = mock.AsyncMock(return_value=None)
        mock_sem.__aexit__ = mock.AsyncMock(return_value=None)

        # Create a list to track not found symbols
        not_found = []

        # Call the process_symbol function
        await process_symbol("INVALID", mock_downloader, not_found, mock_sem, interval="60min")

        # Verify that the downloader was called
        mock_downloader.download.assert_called()

        # Verify that the symbol was added to the not_found list
        self.assertEqual(not_found, ["INVALID"])

    @mock.patch('os.makedirs')
    @mock.patch('os.path.exists')
    @mock.patch('builtins.open', new_callable=mock.mock_open)
    @mock.patch('asyncio.gather')
    @mock.patch('ingesters.IntradayDataIngester.process_symbol')
    @mock.patch('data_manager.symbol_manager.SymbolManager')
    async def test_main_function(self, mock_symbol_manager_class, mock_process_symbol, 
                                mock_gather, mock_open, mock_exists, mock_makedirs):
        """Test the main function of the IntradayDataIngester."""
        # Mock os.path.exists to return True for missing_symbols files
        mock_exists.return_value = True

        # Mock open to return a file with missing symbols
        mock_file = mock.MagicMock()
        mock_file.readlines.return_value = ["MISSING1\n", "MISSING2\n"]
        mock_file.__enter__.return_value = mock_file
        mock_open.return_value = mock_file

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
        self.assertTrue(mock_makedirs.called)

        # Verify that SymbolManager was initialized and used
        mock_symbol_manager.load_russell_1000_symbols.assert_called_once()
        mock_symbol_manager.get_symbols_space_separated.assert_called_once()
        mock_symbol_manager.save_symbols_to_file.assert_called_once_with("symbols.txt")

        # Verify that process_symbol was called
        self.assertTrue(mock_process_symbol.called)

        # Verify that gather was called
        mock_gather.assert_called()

        # Verify that the missing symbols file was written
        self.assertTrue(mock_open.called)

    @mock.patch('ingesters.IntradayDataIngester.generate_month_list')
    @mock.patch('os.makedirs')
    @mock.patch('builtins.open', new_callable=mock.mock_open)
    @mock.patch('pandas.DataFrame.from_dict')
    @mock.patch('pandas.DataFrame.to_pickle')
    async def test_process_symbol_consecutive_empty_months(self, mock_to_pickle, mock_from_dict, 
                                                         mock_open, mock_makedirs, mock_generate_month_list):
        """Test processing a symbol with consecutive empty months."""
        # Mock generate_month_list to return a fixed list of months
        mock_generate_month_list.return_value = ["2023-03", "2023-02", "2023-01", "2022-12", "2022-11"]

        # Mock the DataFrame creation
        mock_df = mock.MagicMock()
        mock_from_dict.return_value = mock_df

        # Create a mock downloader that returns data for some months and empty for others
        mock_downloader = mock.MagicMock()
        
        # First month has data
        first_month_data = dict(self.sample_time_series_data)
        mock_downloader.download.side_effect = [
            # First month has data
            first_month_data,
            # Next 3 months have no data (empty time series)
            {"Meta Data": first_month_data["Meta Data"]},
            {"Meta Data": first_month_data["Meta Data"]},
            {"Meta Data": first_month_data["Meta Data"]},
            # Last month would have data but shouldn't be called due to max_consecutive_empty
        ]

        # Create a mock semaphore
        mock_sem = mock.MagicMock()
        mock_sem.__aenter__ = mock.AsyncMock(return_value=None)
        mock_sem.__aexit__ = mock.AsyncMock(return_value=None)

        # Create a list to track not found symbols
        not_found = []

        # Call the process_symbol function
        await process_symbol("AAPL", mock_downloader, not_found, mock_sem, interval="60min")

        # Verify that the downloader was called only 4 times (not 5)
        # First call + 3 consecutive empty months = 4 calls
        self.assertEqual(mock_downloader.download.call_count, 4)

        # Verify that the JSON file was opened and written
        json_dir = Path(config.DATA_ROOT_DIR) / "intraday" / "json" / "60min"
        mock_open.assert_called_with(json_dir / "AAPL.json", "w")
        mock_open().write.assert_called_once()

        # Verify that the DataFrame was created and saved as pickle
        mock_from_dict.assert_called_once_with(mock.ANY, orient="index")
        pickle_dir = Path(config.DATA_ROOT_DIR) / "intraday" / "pickle" / "60min"
        mock_to_pickle.assert_called_once_with(pickle_dir / "AAPL.pkl.gz", compression="gzip")

        # Verify that the symbol was not added to the not_found list
        self.assertEqual(not_found, [])


class AsyncioTestCase(unittest.TestCase):
    """Base class for asyncio test cases."""

    def run_async(self, coro):
        """Run a coroutine in the event loop."""
        return asyncio.run(coro)


# Modify the TestIntradayDataIngester class to use AsyncioTestCase
TestIntradayDataIngester.__bases__ = (AsyncioTestCase,)


# Wrap async test methods to run them with run_async
for name in dir(TestIntradayDataIngester):
    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestIntradayDataIngester, name)):
        method = getattr(TestIntradayDataIngester, name)

        def wrapper(self, method=method):
            return self.run_async(method(self))

        setattr(TestIntradayDataIngester, name, wrapper)


if __name__ == '__main__':
    unittest.main()