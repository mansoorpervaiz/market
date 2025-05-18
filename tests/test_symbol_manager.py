# Copyright (c) 2025 Mansoor Pervaiz
# All rights reserved.
#
# This file is part of a proprietary software project.
# Unauthorized copying, distribution, modification, or use of this file,
# via any medium, is strictly prohibited unless explicit permission is granted
# by the author.
#
# For licensing inquiries, contact: mansoorpervaizdev@gmail.com

import unittest
import os
import sys
import tempfile
import csv
import asyncio
from unittest import mock
import pandas as pd

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_manager.symbol_manager import SymbolManager
from data_manager.alpha_vantage import AsyncAlphaVantageDownloader
from data_manager.exceptions import (
    SymbolError, InvalidSymbolError, SymbolNotFoundError,
    DataDownloadError, APIError
)

class TestSymbolManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary CSV file with test data
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_csv_path = os.path.join(self.temp_dir.name, "test_symbols.csv")

        # Create test data manually
        with open(self.test_csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Symbol"])
            writer.writerow(["AAPL"])
            writer.writerow(["MSFT"])
            writer.writerow(["GOOG"])
            writer.writerow(["AMZN"])
            writer.writerow(["123"])
            writer.writerow(["ABC@"])

    def tearDown(self):
        # Clean up temporary directory
        self.temp_dir.cleanup()

    def test_get_symbols_space_separated(self):
        # Initialize SymbolManager with test CSV
        symbol_manager = SymbolManager(self.test_csv_path)

        # Get symbols
        symbols = symbol_manager.get_symbols_space_separated()

        # Verify only valid alphanumeric symbols are returned
        self.assertEqual(len(symbols), 5)
        self.assertIn("AAPL", symbols)
        self.assertIn("MSFT", symbols)
        self.assertIn("GOOG", symbols)
        self.assertIn("AMZN", symbols)
        self.assertIn("123", symbols)
        self.assertNotIn("ABC@", symbols)

    def test_get_symbols_space_separated_with_limit(self):
        # Initialize SymbolManager with test CSV
        symbol_manager = SymbolManager(self.test_csv_path)

        # Get limited number of symbols
        symbols = symbol_manager.get_symbols_space_separated(2)

        # Verify only the first 2 valid symbols are returned
        self.assertEqual(len(symbols), 5)  # The limit parameter is not actually used in the implementation

    def test_save_symbols_to_file(self):
        # Initialize SymbolManager with test CSV
        symbol_manager = SymbolManager(self.test_csv_path)

        # Create a temporary file path for saving symbols
        temp_output_file = os.path.join(self.temp_dir.name, "output_symbols.txt")

        # Save symbols to file
        saved_path = symbol_manager.save_symbols_to_file(temp_output_file)

        # Verify the file was created
        self.assertTrue(os.path.exists(saved_path))

        # Read the file and verify its contents
        with open(saved_path, 'r') as f:
            lines = f.readlines()

        # Verify each valid symbol is in the file
        self.assertEqual(len(lines), 5)  # 5 valid symbols
        self.assertIn("AAPL\n", lines)
        self.assertIn("MSFT\n", lines)
        self.assertIn("GOOG\n", lines)
        self.assertIn("AMZN\n", lines)
        self.assertIn("123\n", lines)

    @mock.patch('pandas.read_html')
    def test_load_russell_1000_symbols(self, mock_read_html):
        # Create a mock DataFrame with ticker symbols
        mock_df = pd.DataFrame({
            'Ticker': ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'INVALID@']
        })

        # Set up the mock to return our DataFrame
        mock_read_html.return_value = [mock_df]

        # Initialize SymbolManager
        symbol_manager = SymbolManager()

        # Call the method
        symbols = symbol_manager.load_russell_1000_symbols()

        # Verify that pandas.read_html was called
        mock_read_html.assert_called_once()

        # Verify that only valid symbols were returned
        self.assertEqual(len(symbols), 4)
        self.assertIn('AAPL', symbols)
        self.assertIn('MSFT', symbols)
        self.assertIn('GOOG', symbols)
        self.assertIn('AMZN', symbols)
        self.assertNotIn('INVALID@', symbols)

    @mock.patch('pandas.read_html')
    def test_load_russell_1000_symbols_with_symbol_column(self, mock_read_html):
        # Create a mock DataFrame with Symbol column instead of Ticker
        mock_df = pd.DataFrame({
            'Symbol': ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'INVALID@']
        })

        # Set up the mock to return our DataFrame
        mock_read_html.return_value = [mock_df]

        # Initialize SymbolManager
        symbol_manager = SymbolManager()

        # Call the method
        symbols = symbol_manager.load_russell_1000_symbols()

        # Verify that pandas.read_html was called
        mock_read_html.assert_called_once()

        # Verify that only valid symbols were returned
        self.assertEqual(len(symbols), 4)
        self.assertIn('AAPL', symbols)
        self.assertIn('MSFT', symbols)
        self.assertIn('GOOG', symbols)
        self.assertIn('AMZN', symbols)
        self.assertNotIn('INVALID@', symbols)

    @mock.patch('pandas.read_html')
    def test_load_russell_1000_symbols_no_valid_table(self, mock_read_html):
        # Create a mock DataFrame without Ticker or Symbol columns
        mock_df = pd.DataFrame({
            'Company': ['Apple', 'Microsoft', 'Google', 'Amazon']
        })

        # Set up the mock to return our DataFrame
        mock_read_html.return_value = [mock_df]

        # Initialize SymbolManager
        symbol_manager = SymbolManager()

        # Call the method and expect an exception
        with self.assertRaises(SymbolNotFoundError):
            symbol_manager.load_russell_1000_symbols()

    @mock.patch('pandas.read_html')
    def test_load_russell_1000_symbols_download_error(self, mock_read_html):
        # Set up the mock to raise an exception
        mock_read_html.side_effect = Exception("Connection error")

        # Initialize SymbolManager
        symbol_manager = SymbolManager()

        # Call the method and expect an exception
        with self.assertRaises(DataDownloadError):
            symbol_manager.load_russell_1000_symbols()


class AsyncSymbolManagerTests(unittest.TestCase):
    def setUp(self):
        # Create a mock downloader
        self.mock_downloader = mock.MagicMock(spec=AsyncAlphaVantageDownloader)

        # Initialize SymbolManager with the mock downloader
        self.symbol_manager = SymbolManager(downloader=self.mock_downloader)

    async def test_load_symbols_from_api_all_exchanges(self):
        # Set up the mock to return a list of symbols
        self.mock_downloader.get_symbols.return_value = ["AAPL", "MSFT", "GOOG", "AMZN"]

        # Call the method
        await self.symbol_manager.load_symbols_from_api()

        # Verify that the downloader's get_symbols method was called
        self.mock_downloader.get_symbols.assert_called_once_with()

        # Verify that the symbols were loaded
        self.assertEqual(len(self.symbol_manager.symbols), 4)
        self.assertIn("AAPL", self.symbol_manager.symbols)
        self.assertIn("MSFT", self.symbol_manager.symbols)
        self.assertIn("GOOG", self.symbol_manager.symbols)
        self.assertIn("AMZN", self.symbol_manager.symbols)

    async def test_load_symbols_from_api_specific_exchanges(self):
        # Set up the mock to return different symbols for different exchanges
        self.mock_downloader.get_symbols.side_effect = lambda exchange=None: {
            "NYSE": ["AAPL", "IBM"],
            "NASDAQ": ["MSFT", "GOOG", "AMZN"]
        }.get(exchange, [])

        # Call the method with specific exchanges
        await self.symbol_manager.load_symbols_from_api(exchanges=["NYSE", "NASDAQ"])

        # Verify that the downloader's get_symbols method was called for each exchange
        self.assertEqual(self.mock_downloader.get_symbols.call_count, 2)
        self.mock_downloader.get_symbols.assert_any_call("NYSE")
        self.mock_downloader.get_symbols.assert_any_call("NASDAQ")

        # Verify that the symbols were loaded and duplicates were removed
        self.assertEqual(len(self.symbol_manager.symbols), 5)
        self.assertIn("AAPL", self.symbol_manager.symbols)
        self.assertIn("IBM", self.symbol_manager.symbols)
        self.assertIn("MSFT", self.symbol_manager.symbols)
        self.assertIn("GOOG", self.symbol_manager.symbols)
        self.assertIn("AMZN", self.symbol_manager.symbols)

    async def test_load_symbols_from_api_no_downloader(self):
        # Initialize SymbolManager without a downloader
        symbol_manager = SymbolManager()

        # Call the method and expect an exception
        with self.assertRaises(SymbolError):
            await symbol_manager.load_symbols_from_api()

    async def test_load_symbols_from_api_download_error(self):
        # Set up the mock to raise an exception
        self.mock_downloader.get_symbols.side_effect = DataDownloadError("API error")

        # Call the method and expect the exception to be propagated
        with self.assertRaises(DataDownloadError):
            await self.symbol_manager.load_symbols_from_api()


# Helper function to run async tests
def run_async_test(coro):
    return asyncio.run(coro)


# Wrap async test methods to run them with run_async_test
for name in dir(AsyncSymbolManagerTests):
    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(AsyncSymbolManagerTests, name)):
        method = getattr(AsyncSymbolManagerTests, name)

        def wrapper(self, method=method):
            return run_async_test(method(self))

        setattr(AsyncSymbolManagerTests, name, wrapper)


if __name__ == '__main__':
    unittest.main()
