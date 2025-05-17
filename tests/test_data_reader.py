import unittest
import sys
import os
import json
import asyncio
import pickle
from unittest import mock
from datetime import date, timedelta
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np

from data_manager.data_reader import DataReader, FieldName
from data_manager.alpha_vantage import AsyncAlphaVantageDownloader
from data_manager.exceptions import (
    DataNotFoundError, DataProcessingError, DataFormatError,
    DataDownloadError, APIError
)
from config import config


class TestDataReader(unittest.TestCase):
    """Test cases for the DataReader class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock downloader
        self.mock_downloader = mock.MagicMock(spec=AsyncAlphaVantageDownloader)

        # Create the data reader with the mock downloader
        self.data_reader = DataReader(downloader=self.mock_downloader)

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
                },
                "2023-01-29": {
                    "1. open": "142.0000",
                    "2. high": "143.5000",
                    "3. low": "141.5000",
                    "4. close": "142.5000",
                    "5. adjusted close": "142.5000",
                    "6. volume": "55000000",
                    "7. dividend amount": "0.0000",
                    "8. split coefficient": "1.0000"
                }
            }
        }

        # Create a sample DataFrame that would result from converting the sample data
        dates = pd.date_range(start='2023-01-29', end='2023-01-31', freq='D')
        self.sample_df = pd.DataFrame({
            'open': [142.0000, 143.1600, 142.7000],
            'high': [143.5000, 143.3100, 144.3400],
            'low': [141.5000, 142.0000, 142.2800],
            'close': [142.5000, 143.0000, 144.2900],
            'adjusted_close': [142.5000, 143.0000, 144.2900],
            'volume': [55000000, 64015367, 86903491],
            'dividend_amount': [0.0000, 0.0000, 0.0000],
            'split_coefficient': [1.0000, 1.0000, 1.0000]
        }, index=dates.date)
        # Set the index name to 'date' for consistency with the data reader
        self.sample_df.index.name = 'date'

        # Create a temporary directory for test data
        self.test_data_dir = Path('test_data')
        self.test_data_dir.mkdir(exist_ok=True)

        # Save the original data directory
        self.original_data_pickle_location = config.DATA_PICKLE_LOCATION
        self.original_class_data_pickle_location = DataReader.DATA_PICKLE_LOCATION

        # Set the data directory to our test directory
        config.DATA_PICKLE_LOCATION = str(self.test_data_dir)
        DataReader.DATA_PICKLE_LOCATION = str(self.test_data_dir)

    def tearDown(self):
        """Clean up after tests."""
        # Restore the original data directory
        config.DATA_PICKLE_LOCATION = self.original_data_pickle_location
        DataReader.DATA_PICKLE_LOCATION = self.original_class_data_pickle_location

        # Remove test data files
        for file in self.test_data_dir.glob('*.pkl.gz'):
            file.unlink()

        # Remove the test directory
        self.test_data_dir.rmdir()

    @mock.patch('data_manager.data_reader.DataReader._load_data')
    @mock.patch('data_manager.data_reader.DataReader._download_and_save_data')
    async def test_get_data_from_cache(self, mock_download, mock_load):
        """Test getting data from cache."""
        # Clear the cache to ensure _get_data_uncached is called
        DataReader._data_cache.clear()

        # Set up the mock to return data
        mock_load.return_value = self.sample_df

        # Call get_data
        result = await self.data_reader.get_data(
            symbol='AAPL',
            start_date=date(2023, 1, 29),
            end_date=date(2023, 1, 31)
        )

        # Verify that _load_data was called twice and _download_and_save_data was not
        self.assertEqual(mock_load.call_count, 2)
        # First call is with symbol and filters
        self.assertEqual(mock_load.call_args_list[0][0][0], 'AAPL')
        # Second call is with symbol and columns=['close']
        self.assertEqual(mock_load.call_args_list[1][0][0], 'AAPL')
        self.assertEqual(mock_load.call_args_list[1][1]['columns'], ['close'])
        mock_download.assert_not_called()

        # Verify the result
        pd.testing.assert_frame_equal(result, self.sample_df)

    @mock.patch('data_manager.data_reader.DataReader._load_data')
    @mock.patch('data_manager.data_reader.DataReader._download_and_save_data')
    async def test_get_data_download_when_not_in_cache(self, mock_download, mock_load):
        """Test downloading data when not in cache."""
        # Clear the cache to ensure _get_data_uncached is called
        DataReader._data_cache.clear()

        # Set up the mocks
        mock_load.side_effect = DataNotFoundError("Data not found")
        mock_download.return_value = self.sample_df

        # Call get_data
        result = await self.data_reader.get_data(
            symbol='AAPL',
            start_date=date(2023, 1, 29),
            end_date=date(2023, 1, 31)
        )

        # Verify that both methods were called
        # _load_data is called once with filters, but raises DataNotFoundError
        self.assertEqual(mock_load.call_count, 1)
        self.assertEqual(mock_load.call_args[0][0], 'AAPL')
        # _download_and_save_data is called once with the symbol
        mock_download.assert_called_once_with('AAPL')

        # Verify the result
        pd.testing.assert_frame_equal(result, self.sample_df)

    @mock.patch('data_manager.data_reader.DataReader._load_data')
    @mock.patch('data_manager.data_reader.DataReader._update_with_latest_data')
    async def test_get_data_update_when_outdated(self, mock_update, mock_load):
        """Test updating data when it's outdated."""
        # Clear the cache to ensure _get_data_uncached is called
        DataReader._data_cache.clear()

        # Create outdated data (missing the latest date)
        outdated_df = self.sample_df.iloc[:-1]

        # Set up the mocks
        mock_load.return_value = outdated_df
        mock_update.return_value = self.sample_df

        # Call get_data with a date range that includes dates not in the outdated data
        result = await self.data_reader.get_data(
            symbol='AAPL',
            start_date=date(2023, 1, 29),
            end_date=date(2023, 1, 31)
        )

        # Verify that both methods were called
        # _load_data is called twice in _get_data_uncached
        self.assertEqual(mock_load.call_count, 2)
        # First call is with symbol and filters
        self.assertEqual(mock_load.call_args_list[0][0][0], 'AAPL')
        # Second call is with symbol and columns=['close']
        self.assertEqual(mock_load.call_args_list[1][0][0], 'AAPL')
        self.assertEqual(mock_load.call_args_list[1][1]['columns'], ['close'])
        mock_update.assert_called_once()

        # Verify the result
        pd.testing.assert_frame_equal(result, self.sample_df)

    @mock.patch('data_manager.data_reader.DataReader._convert_dict_to_dataframe')
    async def test_download_and_save_data(self, mock_convert):
        """Test downloading and saving data."""
        # Set up the mocks
        self.mock_downloader.download.return_value = self.sample_time_series_data
        mock_convert.return_value = self.sample_df

        # Mock the _save_data method
        with mock.patch.object(self.data_reader, '_save_data') as mock_save:
            # Call _download_and_save_data
            result = await self.data_reader._download_and_save_data('AAPL')

            # Verify that the downloader was called
            self.mock_downloader.download.assert_called_once_with('AAPL')

            # Verify that the data was converted and saved
            mock_convert.assert_called_once_with(self.sample_time_series_data)
            mock_save.assert_called_once_with('AAPL', self.sample_df)

            # Verify the result
            pd.testing.assert_frame_equal(result, self.sample_df)

    def test_convert_dict_to_dataframe(self):
        """Test converting API response to DataFrame."""
        # Call _convert_dict_to_dataframe
        result = self.data_reader._convert_dict_to_dataframe(self.sample_time_series_data)

        # Verify the result
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 3)  # 3 days of data
        self.assertEqual(result.index.name, 'date')

        # Check column names
        expected_columns = ['open', 'high', 'low', 'close', 'adjusted_close', 
                           'volume', 'dividend_amount', 'split_coefficient']
        self.assertListEqual(list(result.columns), expected_columns)

        # Check values
        self.assertEqual(result.loc[date(2023, 1, 31), 'close'], 144.29)
        self.assertEqual(result.loc[date(2023, 1, 30), 'open'], 143.16)

    def test_save_and_load_data(self):
        """Test saving and loading data."""
        # Save the sample DataFrame
        self.data_reader._save_data('AAPL', self.sample_df)

        # Verify that the file was created
        file_path = Path(config.DATA_PICKLE_LOCATION) / 'AAPL.pkl.gz'
        self.assertTrue(file_path.exists())

        # Load the data
        loaded_df = self.data_reader._load_data('AAPL')

        # Verify the loaded data
        pd.testing.assert_frame_equal(loaded_df, self.sample_df)

    def test_load_data_not_found(self):
        """Test loading data that doesn't exist."""
        # Try to load non-existent data
        with self.assertRaises(DataNotFoundError):
            self.data_reader._load_data('NONEXISTENT')

    async def test_get_mean(self):
        """Test getting mean value for a field."""
        # Mock get_data to return our sample DataFrame
        with mock.patch.object(self.data_reader, 'get_data', return_value=self.sample_df):
            # Call get_mean
            mean_close = await self.data_reader.get_mean(
                symbol='AAPL',
                start_date=date(2023, 1, 29),
                end_date=date(2023, 1, 31),
                field_name=FieldName.CLOSE
            )

            # Verify the result
            expected_mean = self.sample_df['close'].mean()
            self.assertEqual(mean_close, expected_mean)

    async def test_get_sma(self):
        """Test getting simple moving average."""
        # Mock get_data to return our sample DataFrame
        with mock.patch.object(self.data_reader, 'get_data', return_value=self.sample_df):
            # Call get_sma
            sma = await self.data_reader.get_sma(
                symbol='AAPL',
                current_date=date(2023, 1, 31),
                number_of_days=3,
                field_name=FieldName.CLOSE
            )

            # Verify the result
            expected_sma = self.sample_df['close'].mean()
            self.assertEqual(sma, expected_sma)

    async def test_get_value(self):
        """Test getting a specific value."""
        # Mock get_data to return our sample DataFrame
        with mock.patch.object(self.data_reader, 'get_data', return_value=self.sample_df):
            # Call get_value
            value = await self.data_reader.get_value(
                symbol='AAPL',
                for_date=date(2023, 1, 31),
                for_field=FieldName.CLOSE
            )

            # Verify the result
            expected_value = self.sample_df.loc[date(2023, 1, 31), 'close']
            self.assertEqual(value, expected_value)


class AsyncioTestCase(unittest.TestCase):
    """Base class for asyncio test cases."""

    def run_async(self, coro):
        """Run a coroutine in the event loop."""
        return asyncio.run(coro)


# Modify the TestDataReader class to use AsyncioTestCase
TestDataReader.__bases__ = (AsyncioTestCase,)


# Wrap async test methods to run them with run_async
for name in dir(TestDataReader):
    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestDataReader, name)):
        method = getattr(TestDataReader, name)

        def wrapper(self, method=method):
            return self.run_async(method(self))

        setattr(TestDataReader, name, wrapper)


if __name__ == '__main__':
    unittest.main()
