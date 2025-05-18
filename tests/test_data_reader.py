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

    @mock.patch('data_manager.data_reader.DataReader._download_and_save_data')
    async def test_update_with_latest_data_success(self, mock_download_save):
        """Test updating data with latest data from API."""
        # Create a sample DataFrame with older data
        dates = pd.date_range(start='2023-01-01', end='2023-01-10', freq='D')
        old_df = pd.DataFrame({
            'close': [100.0] * len(dates),
            'open': [95.0] * len(dates),
            'high': [105.0] * len(dates),
            'low': [90.0] * len(dates),
            'volume': [1000000] * len(dates),
        }, index=dates.date)
        old_df.index.name = 'date'

        # Create a sample DataFrame with newer data
        new_dates = pd.date_range(start='2023-01-11', end='2023-01-15', freq='D')
        new_df = pd.DataFrame({
            'close': [110.0] * len(new_dates),
            'open': [105.0] * len(new_dates),
            'high': [115.0] * len(new_dates),
            'low': [100.0] * len(new_dates),
            'volume': [1200000] * len(new_dates),
        }, index=new_dates.date)
        new_df.index.name = 'date'

        # Set up the mock to return the new data
        self.mock_downloader.download.return_value = self.sample_time_series_data
        mock_download_save.return_value = new_df

        # Mock the _convert_dict_to_dataframe method
        with mock.patch.object(self.data_reader, '_convert_dict_to_dataframe', return_value=new_df):
            # Mock the _save_data method
            with mock.patch.object(self.data_reader, '_save_data') as mock_save:
                # Call _update_with_latest_data
                result = await self.data_reader._update_with_latest_data(
                    symbol='AAPL',
                    last_date_in_df=date(2023, 1, 10),
                    previous_data=old_df
                )

                # Verify that the downloader was called
                self.mock_downloader.download.assert_called_once_with('AAPL')

                # Verify that the data was saved
                mock_save.assert_called_once()

                # Verify the result contains both old and new data
                self.assertEqual(len(result), len(old_df) + len(new_df))
                self.assertEqual(result.loc[date(2023, 1, 1), 'close'], 100.0)
                self.assertEqual(result.loc[date(2023, 1, 15), 'close'], 110.0)

    @mock.patch('data_manager.data_reader.DataReader._download_and_save_data')
    async def test_update_with_latest_data_no_new_data(self, mock_download_save):
        """Test updating data when there's no new data available."""
        # Create a sample DataFrame
        dates = pd.date_range(start='2023-01-01', end='2023-01-10', freq='D')
        df = pd.DataFrame({
            'close': [100.0] * len(dates),
            'open': [95.0] * len(dates),
            'high': [105.0] * len(dates),
            'low': [90.0] * len(dates),
            'volume': [1000000] * len(dates),
        }, index=dates.date)
        df.index.name = 'date'

        # Set up the mock to return data with no new dates
        self.mock_downloader.download.return_value = self.sample_time_series_data

        # Mock the _convert_dict_to_dataframe method to return data with no new dates
        with mock.patch.object(self.data_reader, '_convert_dict_to_dataframe', return_value=df):
            # Call _update_with_latest_data
            result = await self.data_reader._update_with_latest_data(
                symbol='AAPL',
                last_date_in_df=date(2023, 1, 10),
                previous_data=df
            )

            # Verify that the downloader was called
            self.mock_downloader.download.assert_called_once_with('AAPL')

            # Verify the result is the same as the input data
            pd.testing.assert_frame_equal(result, df)

    @mock.patch('data_manager.data_reader.DataReader._download_and_save_data')
    async def test_update_with_latest_data_download_error(self, mock_download_save):
        """Test updating data when there's an error downloading new data."""
        # Create a sample DataFrame
        dates = pd.date_range(start='2023-01-01', end='2023-01-10', freq='D')
        df = pd.DataFrame({
            'close': [100.0] * len(dates),
            'open': [95.0] * len(dates),
            'high': [105.0] * len(dates),
            'low': [90.0] * len(dates),
            'volume': [1000000] * len(dates),
        }, index=dates.date)
        df.index.name = 'date'

        # Set up the mock to raise an exception
        self.mock_downloader.download.side_effect = DataDownloadError("API error")

        # Call _update_with_latest_data
        result = await self.data_reader._update_with_latest_data(
            symbol='AAPL',
            last_date_in_df=date(2023, 1, 10),
            previous_data=df
        )

        # Verify that the downloader was called
        self.mock_downloader.download.assert_called_once_with('AAPL')

        # Verify the result is the same as the input data (no update due to error)
        pd.testing.assert_frame_equal(result, df)

    @mock.patch('data_manager.data_reader.DataReader._load_data')
    @mock.patch('data_manager.data_reader.DataReader._download_and_save_data')
    @mock.patch('data_manager.data_reader.DataReader._update_with_latest_data')
    async def test_get_data_uncached_load_success(self, mock_update, mock_download, mock_load):
        """Test _get_data_uncached when data is successfully loaded."""
        # Clear the cache
        DataReader._data_cache.clear()

        # Set up the mocks
        mock_load.return_value = self.sample_df

        # Call _get_data_uncached
        result = await self.data_reader._get_data_uncached(
            symbol='AAPL',
            start_date=date(2023, 1, 29),
            end_date=date(2023, 1, 31)
        )

        # Verify that _load_data was called twice
        self.assertEqual(mock_load.call_count, 2)
        # First call is with symbol and filters
        self.assertEqual(mock_load.call_args_list[0][0][0], 'AAPL')
        # Second call is with symbol and columns=['close']
        self.assertEqual(mock_load.call_args_list[1][0][0], 'AAPL')
        self.assertEqual(mock_load.call_args_list[1][1]['columns'], ['close'])

        # Verify that _download_and_save_data was not called
        mock_download.assert_not_called()

        # Verify the result
        pd.testing.assert_frame_equal(result, self.sample_df)

    @mock.patch('data_manager.data_reader.DataReader._load_data')
    @mock.patch('data_manager.data_reader.DataReader._download_and_save_data')
    async def test_get_data_uncached_download_when_not_found(self, mock_download, mock_load):
        """Test _get_data_uncached when data is not found locally."""
        # Clear the cache
        DataReader._data_cache.clear()

        # Set up the mocks
        mock_load.side_effect = DataNotFoundError("Data not found")
        mock_download.return_value = self.sample_df

        # Call _get_data_uncached
        result = await self.data_reader._get_data_uncached(
            symbol='AAPL',
            start_date=date(2023, 1, 29),
            end_date=date(2023, 1, 31)
        )

        # Verify that _load_data was called once
        mock_load.assert_called_once()

        # Verify that _download_and_save_data was called
        mock_download.assert_called_once_with('AAPL')

        # Verify the result
        pd.testing.assert_frame_equal(result, self.sample_df)

    @mock.patch('data_manager.data_reader.DataReader._load_data')
    @mock.patch('data_manager.data_reader.DataReader._download_and_save_data')
    @mock.patch('data_manager.data_reader.DataReader._update_with_latest_data')
    async def test_get_data_uncached_update_when_outdated(self, mock_update, mock_download, mock_load):
        """Test _get_data_uncached when data is outdated."""
        # Clear the cache
        DataReader._data_cache.clear()

        # Create outdated data (missing the latest date)
        outdated_df = self.sample_df.iloc[:-1]

        # Set up the mocks
        mock_load.return_value = outdated_df
        mock_update.return_value = self.sample_df

        # Call _get_data_uncached
        result = await self.data_reader._get_data_uncached(
            symbol='AAPL',
            start_date=date(2023, 1, 29),
            end_date=date(2023, 1, 31)
        )

        # Verify that _load_data was called twice
        self.assertEqual(mock_load.call_count, 2)

        # Verify that _update_with_latest_data was called
        mock_update.assert_called_once()

        # Verify the result
        pd.testing.assert_frame_equal(result, self.sample_df)

    @mock.patch('pandas.read_parquet')
    @mock.patch('os.path.exists')
    @mock.patch('data_manager.data_reader.DataReader._download_and_save_data')
    @mock.patch('data_manager.data_reader.DataReader._load_data')
    async def test_get_data_chunked_existing_parquet(self, mock_load, mock_download, mock_exists, mock_read_parquet):
        """Test _get_data_chunked with existing parquet file."""
        # Set up the mocks
        mock_exists.return_value = True

        # Create a mock DataFrame with dates
        dates = pd.date_range(start='2023-01-01', end='2023-01-10', freq='D')
        df_index = pd.DataFrame(index=dates.date)
        df_index.index.name = 'date'

        # Create chunks of data
        chunk1 = self.sample_df.iloc[:1]
        chunk2 = self.sample_df.iloc[1:2]
        chunk3 = self.sample_df.iloc[2:]

        # Set up the mock to return the index DataFrame and then chunks
        mock_read_parquet.return_value = df_index
        mock_load.side_effect = [chunk1, chunk2, chunk3]

        # Call _get_data_chunked
        chunks = []
        async for chunk in self.data_reader._get_data_chunked(
            symbol='AAPL',
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 10),
            chunk_size=1
        ):
            chunks.append(chunk)

        # Verify that read_parquet was called
        mock_read_parquet.assert_called_once()

        # Verify that _load_data was called for each chunk
        self.assertEqual(mock_load.call_count, 3)

        # Verify that _download_and_save_data was not called
        mock_download.assert_not_called()

        # Verify the chunks
        self.assertEqual(len(chunks), 3)
        pd.testing.assert_frame_equal(chunks[0], chunk1)
        pd.testing.assert_frame_equal(chunks[1], chunk2)
        pd.testing.assert_frame_equal(chunks[2], chunk3)

    @mock.patch('os.path.exists')
    @mock.patch('pandas.read_pickle')
    @mock.patch('data_manager.data_reader.DataReader._save_data_parquet')
    async def test_get_data_chunked_convert_from_pickle(self, mock_save_parquet, mock_read_pickle, mock_exists):
        """Test _get_data_chunked converting from pickle to parquet."""
        # Set up the mocks to indicate parquet doesn't exist but pickle does
        mock_exists.side_effect = lambda path: '.pkl.gz' in path
        mock_read_pickle.return_value = self.sample_df

        # Mock pandas.read_parquet to return empty DataFrame for the first call (checking dates)
        # and then return chunks for subsequent calls
        with mock.patch('pandas.read_parquet') as mock_read_parquet:
            # Set up mock to return empty DataFrame with date index
            empty_df = pd.DataFrame(index=[])
            empty_df.index.name = 'date'
            mock_read_parquet.return_value = empty_df

            # Call _get_data_chunked
            chunks = []
            async for chunk in self.data_reader._get_data_chunked(
                symbol='AAPL',
                start_date=date(2023, 1, 29),
                end_date=date(2023, 1, 31),
                chunk_size=1
            ):
                chunks.append(chunk)

        # Verify that read_pickle was called
        mock_read_pickle.assert_called_once()

        # Verify that _save_data_parquet was called
        mock_save_parquet.assert_called_once()

        # Verify the chunks (should be empty since we mocked an empty DataFrame)
        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0].empty)


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
