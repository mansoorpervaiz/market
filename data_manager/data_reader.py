# Copyright (c) 2025 Mansoor Pervaiz
# All rights reserved.
#
# This file is part of a proprietary software project.
# Unauthorized copying, distribution, modification, or use of this file,
# via any medium, is strictly prohibited unless explicit permission is granted
# by the author.
#
# For licensing inquiries, contact: mansoorpervaizdev@gmail.com

"""
Data Reader Module for Market Data Management.

This module provides functionality for loading, saving, and processing market data.
It handles data retrieval from local storage and external APIs (Alpha Vantage),
with capabilities for updating existing data with the latest information.
"""

import os
import asyncio
import json
import functools
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Tuple, Optional, Any

import pandas as pd
from enum import Enum
from cachetools import TTLCache, cached

from data_manager.alpha_vantage import AsyncAlphaVantageDownloader
from data_manager.exceptions import (
    DataNotFoundError, DataProcessingError, DataFormatError,
    DataDownloadError, APIError
)
from logger import get_logger
from config import config
from interfaces.data_access.data_reader_interface import DataReaderInterface
from interfaces.data_access.downloader_interface import DownloaderInterface

# Initialize logger
logger = get_logger(__name__)


class FieldName(Enum):
    """
    Enumeration of field names used in market data.

    These field names are used to access specific columns in the market data DataFrame
    and provide a standardized way to refer to different types of price and volume data.
    """
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    ADJUSTED_CLOSE = "adjusted_close"
    VOLUME = "volume"


class DataReader(DataReaderInterface):
    """
    A class for reading, processing, and managing market data.

    This class implements the DataReaderInterface and provides methods for:
    - Loading market data from local storage
    - Downloading market data from external APIs
    - Processing and converting market data to usable formats
    - Updating existing data with the latest information
    - Calculating statistics on market data

    Optimizations:
    - Efficient storage: Uses parquet format with snappy compression for better performance
      and smaller file sizes compared to pickle files
    - Caching: Implements TTL-based caching for frequently accessed data to reduce disk I/O
    - Indexing: Optimizes parquet files with proper indexing for efficient date range queries
    - Backward compatibility: Maintains pickle format for compatibility with existing code

    The class handles data caching to improve performance and manages error handling
    for various data access scenarios.
    """

    DATA_PICKLE_LOCATION = config.DATA_PICKLE_LOCATION
    DATA_JSON_LOCATION = config.DATA_JSON_LOCATION
    DATA_PARQUET_LOCATION = config.DATA_PARQUET_LOCATION

    # Create a cache for storing frequently accessed data
    # The cache is keyed by (symbol, start_date, end_date) tuples
    _data_cache = TTLCache(
        maxsize=config.CACHE_MAX_SIZE,
        ttl=config.CACHE_TTL
    )

    def __init__(self, downloader: DownloaderInterface = None) -> None:
        """
        Initialize the DataReader with an optional data downloader.

        Args:
            downloader: An optional implementation of DownloaderInterface for fetching market data.
                        If not provided, an AsyncAlphaVantageDownloader will be used by default.
        """
        self.alpha_vantage_downloader = downloader if downloader else AsyncAlphaVantageDownloader()
        self.loaded_data = None
        self.loaded_data_symbol = None

        # Ensure data directories exist
        os.makedirs(self.DATA_PICKLE_LOCATION, exist_ok=True)
        os.makedirs(self.DATA_JSON_LOCATION, exist_ok=True)
        os.makedirs(self.DATA_PARQUET_LOCATION, exist_ok=True)

    def _load_data_parquet(self, symbol: str, columns=None, filters=None) -> pd.DataFrame:
        """
        Load market data for a given symbol from parquet storage.

        Args:
            symbol: The stock symbol to load data for (e.g., 'MSFT', 'AAPL')
            columns: List of columns to load (None loads all columns)
            filters: Filters to apply when loading data (e.g., date range)

        Returns:
            A pandas DataFrame containing the market data with standardized column names

        Raises:
            DataNotFoundError: If the data file for the symbol doesn't exist
            DataProcessingError: If there's an error processing the data
        """
        try:
            file_path = os.path.join(self.DATA_PARQUET_LOCATION, f"{symbol}.parquet")
            df = pd.read_parquet(file_path, columns=columns, filters=filters)
            logger.debug(f"Loaded parquet data for {symbol}, columns: {df.columns.tolist()}")

            # Ensure index is datetime.date for consistency
            if not all(isinstance(idx, date) for idx in df.index):
                df.index = pd.to_datetime(df.index).date

            # Add back dividend_amount and split_coefficient columns if they're missing
            # This ensures consistency with data loaded from pickle
            if 'dividend_amount' not in df.columns:
                df['dividend_amount'] = 0.0

            if 'split_coefficient' not in df.columns:
                df['split_coefficient'] = 1.0

            return df
        except FileNotFoundError:
            logger.warning(f"Parquet file for {symbol} not found")
            raise DataNotFoundError(f"Data file for symbol {symbol} not found")
        except Exception as e:
            logger.error(f"Error loading parquet data for {symbol}: {str(e)}")
            raise DataProcessingError(f"Error loading data for {symbol}: {str(e)}") from e

    def _load_data_pickle(self, symbol: str) -> pd.DataFrame:
        """
        Load market data for a given symbol from pickle storage (legacy format).

        Args:
            symbol: The stock symbol to load data for (e.g., 'MSFT', 'AAPL')

        Returns:
            A pandas DataFrame containing the market data with standardized column names

        Raises:
            DataNotFoundError: If the data file for the symbol doesn't exist
            DataProcessingError: If there's an error processing the data
        """
        try:
            file_path = os.path.join(self.DATA_PICKLE_LOCATION, f"{symbol}.pkl.gz")
            df = pd.read_pickle(file_path)
            logger.debug(f"Loaded pickle data for {symbol}, columns: {df.columns.tolist()}")

            # Rename columns to match what the code expects
            if '4. close' in df.columns and 'close' not in df.columns:
                df.rename(
                    columns={
                        '1. open': FieldName.OPEN.value,
                        '2. high': FieldName.HIGH.value,
                        '3. low': FieldName.LOW.value,
                        '4. close': FieldName.CLOSE.value,
                        '5. adjusted close': FieldName.ADJUSTED_CLOSE.value,
                        '6. volume': FieldName.VOLUME.value
                    },
                    inplace=True)

                # Convert string values to numeric
                for col in [FieldName.OPEN.value, FieldName.HIGH.value, FieldName.LOW.value, 
                           FieldName.CLOSE.value, FieldName.ADJUSTED_CLOSE.value]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')

                # Convert volume to int if it exists
                if FieldName.VOLUME.value in df.columns:
                    df[FieldName.VOLUME.value] = pd.to_numeric(df[FieldName.VOLUME.value], errors='coerce').astype('Int64')

            # Ensure index is datetime.date for consistency
            if not all(isinstance(idx, date) for idx in df.index):
                df.index = pd.to_datetime(df.index).date

            return df
        except FileNotFoundError:
            logger.warning(f"Pickle file for {symbol} not found")
            raise DataNotFoundError(f"Data file for symbol {symbol} not found")
        except Exception as e:
            logger.error(f"Error loading pickle data for {symbol}: {str(e)}")
            raise DataProcessingError(f"Error loading data for {symbol}: {str(e)}") from e

    def _load_data(self, symbol: str, columns=None, filters=None) -> pd.DataFrame:
        """
        Load market data for a given symbol from local storage.

        This method tries to load from parquet first, then falls back to pickle if needed.

        Args:
            symbol: The stock symbol to load data for (e.g., 'MSFT', 'AAPL')
            columns: List of columns to load (None loads all columns)
            filters: Filters to apply when loading data (e.g., date range)

        Returns:
            A pandas DataFrame containing the market data with standardized column names

        Raises:
            DataNotFoundError: If the data file for the symbol doesn't exist
            DataProcessingError: If there's an error processing the data
        """
        try:
            # Try to load from parquet first
            try:
                return self._load_data_parquet(symbol, columns=columns, filters=filters)
            except DataNotFoundError:
                # If parquet file doesn't exist, try pickle
                logger.info(f"Parquet file for {symbol} not found, trying pickle")
                df = self._load_data_pickle(symbol)

                # Save to parquet for future use
                self._save_data_parquet(symbol, df)
                logger.info(f"Converted pickle data for {symbol} to parquet format")

                # Apply filters if provided
                if filters:
                    for column, op, value in filters:
                        if op == '>=':
                            df = df[df[column] >= value]
                        elif op == '<=':
                            df = df[df[column] <= value]
                        elif op == '==':
                            df = df[df[column] == value]

                # Select columns if provided
                if columns:
                    df = df[columns]

                return df
        except DataNotFoundError:
            # Re-raise if neither format is found
            raise
        except Exception as e:
            logger.error(f"Error loading data for {symbol}: {str(e)}")
            raise DataProcessingError(f"Error loading data for {symbol}: {str(e)}") from e

    def _save_data_parquet(self, symbol: str, symbol_data: pd.DataFrame) -> None:
        """
        Save the DataFrame to parquet format with optimized settings and indexing.

        This method saves data with proper indexing on the date column to improve
        query performance for historical data lookups.

        Args:
            symbol: Stock symbol (e.g., 'MSFT', 'AAPL')
            symbol_data: DataFrame containing stock data
        """
        try:
            # Create a copy to avoid modifying the original
            df = symbol_data.copy()

            # Ensure the index is named for better querying
            if df.index.name is None:
                df.index.name = 'date'

            # Sort by date for optimal querying
            df = df.sort_index()

            # Remove problematic columns that cause issues with parquet format
            columns_to_drop = []
            if 'dividend_amount' in df.columns:
                columns_to_drop.append('dividend_amount')
            if 'split_coefficient' in df.columns:
                columns_to_drop.append('split_coefficient')

            if columns_to_drop:
                # Create a new copy without the problematic columns
                df_for_parquet = df.drop(columns=columns_to_drop)
                logger.debug(f"Dropped columns {columns_to_drop} for parquet saving")
            else:
                df_for_parquet = df

            # Save with compression and row group optimization
            file_path = os.path.join(self.DATA_PARQUET_LOCATION, f"{symbol}.parquet")
            df_for_parquet.to_parquet(
                file_path,
                compression='snappy',  # Good balance of compression and speed
                index=True,
                engine='pyarrow',
                # Set row group size for optimal querying by date ranges
                # This helps with date range filtering performance
                row_group_size=100  # Adjust based on typical query patterns
            )
            logger.debug(f"Saved parquet data for {symbol} with optimized indexing")
        except Exception as e:
            logger.error(f"Error saving parquet data for {symbol}: {str(e)}")
            raise DataProcessingError(f"Error saving parquet data for {symbol}: {str(e)}") from e

    def _save_data_pickle(self, symbol: str, symbol_data: pd.DataFrame) -> None:
        """
        Save the DataFrame to pickle format (legacy format).

        Args:
            symbol: Stock symbol (e.g., 'MSFT', 'AAPL')
            symbol_data: DataFrame containing stock data
        """
        try:
            # Create a copy to avoid modifying the original
            df = symbol_data.copy()

            # Ensure the index is named for consistency
            if df.index.name is None:
                df.index.name = 'date'

            file_path = os.path.join(self.DATA_PICKLE_LOCATION, f"{symbol}.pkl.gz")
            df.to_pickle(file_path)
            logger.debug(f"Saved pickle data for {symbol}")
        except Exception as e:
            logger.error(f"Error saving pickle data for {symbol}: {str(e)}")
            raise DataProcessingError(f"Error saving pickle data for {symbol}: {str(e)}") from e

    def _save_data(self, symbol: str, symbol_data: pd.DataFrame) -> None:
        """
        Save the DataFrame to both parquet and pickle formats.

        Args:
            symbol: Stock symbol (e.g., 'MSFT', 'AAPL')
            symbol_data: DataFrame containing stock data
        """
        # Save to parquet (primary format)
        self._save_data_parquet(symbol, symbol_data)

        # Also save to pickle for backward compatibility
        self._save_data_pickle(symbol, symbol_data)

    async def _download_and_save_data(self, symbol: str) -> pd.DataFrame:
        """
        Download market data for a symbol from the API and save it to local storage.

        Args:
            symbol: The stock symbol to download data for (e.g., 'MSFT', 'AAPL')

        Returns:
            A pandas DataFrame containing the downloaded market data

        Raises:
            DataDownloadError: If there's an error downloading the data from the API
            APIError: If there's an error with the API request
            DataFormatError: If the downloaded data is empty or in an invalid format
            DataProcessingError: If there's an error processing or saving the data
        """
        try:
            symbol_data_dict = await self.alpha_vantage_downloader.download(symbol)

            # Save the original JSON response
            if symbol_data_dict:
                # Ensure the JSON directory exists
                os.makedirs(self.DATA_JSON_LOCATION, exist_ok=True)

                try:
                    # Save the JSON data
                    json_path = os.path.join(self.DATA_JSON_LOCATION, f"{symbol}.json")
                    with open(json_path, "w") as f:
                        json.dump(symbol_data_dict, f)
                    logger.info(f"Saved JSON data for {symbol}")
                except (IOError, PermissionError) as e:
                    logger.error(f"Error saving JSON data for {symbol}: {str(e)}")
                    # Continue execution even if JSON saving fails

            # Convert to DataFrame
            dataframe = self._convert_dict_to_dataframe(symbol_data_dict)

            # Only save if we have valid data
            if not dataframe.empty:
                try:
                    self._save_data(symbol, dataframe)
                    logger.info(f"Saved data for {symbol}")
                except (IOError, PermissionError) as e:
                    logger.error(f"Error saving data for {symbol}: {str(e)}")
                    raise DataProcessingError(f"Error saving data for {symbol}: {str(e)}") from e
            else:
                logger.error(f"Error processing {symbol}: 'Time Series (Daily)' data is empty or invalid")
                raise DataFormatError(f"Invalid or empty data format for {symbol}")

            return dataframe
        except (DataDownloadError, APIError) as e:
            # These exceptions are already properly formatted, just log and re-raise
            logger.error(f"Error downloading data for {symbol}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing data for {symbol}: {str(e)}")
            raise DataProcessingError(f"Unexpected error processing data for {symbol}: {str(e)}") from e
        finally:
            # Ensure resources are properly cleaned up
            await self.alpha_vantage_downloader.close_session()
            # Clear any temporary data that might be in memory
            symbol_data_dict = None

    async def _update_with_latest_data(self, symbol: str, last_date_in_df: date, previous_data: pd.DataFrame) -> pd.DataFrame:
        """
        Update existing market data with the latest data from the API.

        Args:
            symbol: The stock symbol to update data for (e.g., 'MSFT', 'AAPL')
            last_date_in_df: The most recent date in the existing data
            previous_data: The existing DataFrame containing historical market data

        Returns:
            A pandas DataFrame containing the updated market data (merged with previous data)

        Raises:
            DataProcessingError: If there's an error processing or saving the updated data
        """
        try:
            symbol_data_dict = await self.alpha_vantage_downloader.download(symbol)

            # Save the original JSON response
            if symbol_data_dict:
                # Ensure the JSON directory exists
                os.makedirs(self.DATA_JSON_LOCATION, exist_ok=True)

                try:
                    # Save the JSON data
                    json_path = os.path.join(self.DATA_JSON_LOCATION, f"{symbol}.json")
                    with open(json_path, "w") as f:
                        json.dump(symbol_data_dict, f)
                    logger.info(f"Updated JSON data for {symbol}")
                except (IOError, PermissionError) as e:
                    logger.error(f"Error saving JSON data for {symbol}: {str(e)}")
                    # Continue execution even if JSON saving fails

            recent_data = self._convert_dict_to_dataframe(symbol_data_dict)

            # If we couldn't get valid data, return the previous data
            if recent_data.empty:
                logger.warning(f"No new data available for {symbol}, using previous data")
                return previous_data

            try:
                # Ensure both dataframes have datetime.date indices
                if not all(isinstance(idx, date) for idx in previous_data.index):
                    previous_data.index = pd.to_datetime(previous_data.index).date

                if not all(isinstance(idx, date) for idx in recent_data.index):
                    recent_data.index = pd.to_datetime(recent_data.index).date

                mask = (recent_data.index > last_date_in_df)
                df_with_new_data = recent_data.loc[mask]

                # Only update if we have new data
                if not df_with_new_data.empty:
                    updated_data = pd.concat([previous_data, df_with_new_data]).drop_duplicates().sort_index()
                    try:
                        self._save_data(symbol, updated_data)
                        logger.info(f"Updated pickle data for {symbol}")
                    except (IOError, PermissionError) as e:
                        logger.error(f"Error saving updated data for {symbol}: {str(e)}")
                        raise DataProcessingError(f"Error saving updated data for {symbol}: {str(e)}") from e
                    return updated_data
                else:
                    logger.info(f"No new data available for {symbol} after {last_date_in_df}")
                    return previous_data
            except Exception as e:
                logger.error(f"Error processing data update for {symbol}: {str(e)}")
                raise DataProcessingError(f"Error processing data update for {symbol}: {str(e)}") from e
        except (DataDownloadError, APIError) as e:
            # These exceptions are already properly formatted, just log and return previous data
            logger.error(f"Error downloading updated data for {symbol}: {str(e)}")
            return previous_data
        except Exception as e:
            logger.error(f"Unexpected error updating data for {symbol}: {str(e)}")
            raise DataProcessingError(f"Unexpected error updating data for {symbol}: {str(e)}") from e
        finally:
            # Ensure resources are properly cleaned up
            await self.alpha_vantage_downloader.close_session()
            # Clear any temporary data that might be in memory
            symbol_data_dict = None

    def _convert_dict_to_dataframe(self, symbol_data, include_adjusted_close=True):
        """
        Convert dictionary data from API response to a pandas DataFrame.

        Args:
            symbol_data: Dictionary containing stock data from API
            include_adjusted_close: Boolean indicating whether to include adjusted close in the result

        Returns:
            pandas DataFrame with stock data
        """
        # Determine columns based on whether adjusted close is included
        columns = [
            FieldName.OPEN.value,
            FieldName.HIGH.value,
            FieldName.LOW.value,
            FieldName.CLOSE.value,
            FieldName.VOLUME.value
        ]

        if include_adjusted_close:
            columns.insert(4, FieldName.ADJUSTED_CLOSE.value)

        # Check if the response contains the expected data
        if not symbol_data:
            logger.error("Empty response data received")
            # Return an empty DataFrame with the expected columns
            return pd.DataFrame(columns=columns)

        if "Time Series (Daily)" not in symbol_data:
            logger.error(f"Invalid data format: 'Time Series (Daily)' not found in response")
            # Log the keys that are present to help with debugging
            logger.debug(f"Available keys in response: {list(symbol_data.keys())}")
            # Return an empty DataFrame with the expected columns
            return pd.DataFrame(columns=columns)

        # Create DataFrame from dictionary
        dataframe = pd.DataFrame.from_dict(symbol_data["Time Series (Daily)"], dtype=float, orient='index')

        # Define column mappings based on whether adjusted close is included
        column_mappings = {
            '1. open': FieldName.OPEN.value,
            '2. high': FieldName.HIGH.value,
            '3. low': FieldName.LOW.value,
            '4. close': FieldName.CLOSE.value,
        }

        if include_adjusted_close:
            column_mappings['5. adjusted close'] = FieldName.ADJUSTED_CLOSE.value
            column_mappings['6. volume'] = FieldName.VOLUME.value
            column_mappings['7. dividend amount'] = 'dividend_amount'
            column_mappings['8. split coefficient'] = 'split_coefficient'
        else:
            column_mappings['5. volume'] = FieldName.VOLUME.value

        dataframe.rename(columns=column_mappings, inplace=True)

        # Convert dividend_amount and split_coefficient to numeric
        if include_adjusted_close:
            # Convert dividend_amount to numeric
            if 'dividend_amount' in dataframe.columns:
                dataframe['dividend_amount'] = pd.to_numeric(dataframe['dividend_amount'], errors='coerce')

            # Convert split_coefficient to numeric
            if 'split_coefficient' in dataframe.columns:
                dataframe['split_coefficient'] = pd.to_numeric(dataframe['split_coefficient'], errors='coerce')

        # Convert volume to integer if it exists
        if 'volume' in dataframe.columns:
            dataframe['volume'] = dataframe['volume'].astype(int)

        # Convert index to datetime.date
        dataframe.index = pd.to_datetime(dataframe.index).date
        dataframe.index.name = 'date'
        return dataframe

    # Cache key function for the get_data method
    def _get_data_cache_key(self, symbol: str, start_date: date, end_date: date) -> Tuple[str, date, date]:
        """
        Generate a cache key for the get_data method.

        Args:
            symbol: Stock symbol
            start_date: Start date for the data range
            end_date: End date for the data range

        Returns:
            A tuple that can be used as a cache key
        """
        return (symbol, start_date, end_date)

    async def _get_data_uncached(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        """
        Get market data for a symbol within a specified date range (uncached version).

        This method handles loading data from local storage or downloading it if necessary.
        It also updates existing data if the requested end date is more recent than the
        available data.

        Args:
            symbol: Stock symbol (e.g., 'MSFT', 'AAPL')
            start_date: Start date for the data range
            end_date: End date for the data range

        Returns:
            A pandas DataFrame containing the market data for the specified date range

        Raises:
            DataNotFoundError: If data cannot be found or downloaded
            DataProcessingError: If there's an error processing the data
        """
        try:
            # Check if we need to load data (different symbol or data not loaded yet)
            if self.loaded_data_symbol != symbol or self.loaded_data is None:
                try:
                    # Create date filters to only load the data we need
                    filters = [
                        ('date', '>=', start_date),
                        ('date', '<=', end_date)
                    ]

                    # Load only the data for the requested date range
                    dataframe = self._load_data(symbol, filters=filters)
                    logger.info(f"Loaded filtered data for {symbol} from local storage")

                    # Check if we need to update with latest data
                    try:
                        # Load just the max date to check if we need to update
                        max_date_df = self._load_data(symbol, columns=['close'])
                        last_date_in_df = max_date_df.index.max() if not max_date_df.empty else None

                        # Only try to update if we have a valid last_date_in_df and it's before end_date
                        if last_date_in_df is not None and last_date_in_df < end_date:
                            try:
                                # Only update the data we don't have yet
                                new_data = await self._update_with_latest_data(
                                    symbol=symbol,
                                    last_date_in_df=last_date_in_df,
                                    previous_data=max_date_df
                                )

                                # Filter the new data to only include dates we need
                                mask = (new_data.index >= start_date) & (new_data.index <= end_date)
                                new_data_filtered = new_data.loc[mask]

                                # Combine with existing data if needed
                                if not new_data_filtered.empty:
                                    dataframe = pd.concat([dataframe, new_data_filtered]).drop_duplicates().sort_index()
                            except Exception as e:
                                # Log the error but continue with the data we have
                                logger.warning(f"Failed to update data for {symbol}: {str(e)}")
                    except Exception as e:
                        logger.warning(f"Error checking for updates for {symbol}: {str(e)}")

                except DataNotFoundError:
                    # did not find data on local disk, downloading and saving it
                    logger.info(f"Data for {symbol} not found locally. Downloading from Alpha Vantage...")
                    try:
                        dataframe = await self._download_and_save_data(symbol)
                        logger.info(f"Downloaded and saved data for {symbol}")

                        # Filter to the requested date range
                        mask = (dataframe.index >= start_date) & (dataframe.index <= end_date)
                        dataframe = dataframe.loc[mask]
                    except (DataDownloadError, APIError) as e:
                        logger.error(f"Failed to download data for {symbol}: {str(e)}")
                        raise DataNotFoundError(f"Could not find or download data for {symbol}") from e

                # Store only the data for the requested date range
                self.loaded_data_symbol = symbol
                self.loaded_data = dataframe

                # Ensure index is datetime.date for comparison
                if not dataframe.empty and not all(isinstance(idx, date) for idx in dataframe.index):
                    dataframe.index = pd.to_datetime(dataframe.index).date

            else:
                # We already have data loaded for this symbol, filter by date range
                mask = (self.loaded_data.index >= start_date) & (self.loaded_data.index <= end_date)
                dataframe = self.loaded_data.loc[mask]

            # Check if we have data for the requested date range
            if dataframe.empty:
                logger.warning(f"No data found for {symbol} between {start_date} and {end_date}")

            return dataframe
        except (DataNotFoundError, DataProcessingError) as e:
            # Re-raise these exceptions as they are already properly formatted
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting data for {symbol}: {str(e)}")
            raise DataProcessingError(f"Unexpected error getting data for {symbol}: {str(e)}") from e

    async def _get_data_chunked(self, symbol: str, start_date: date, end_date: date, chunk_size: int):
        """
        Get market data for a symbol in chunks to avoid loading the entire dataset into memory.

        Args:
            symbol: Stock symbol (e.g., 'MSFT', 'AAPL')
            start_date: Start date for the data range
            end_date: End date for the data range
            chunk_size: Number of rows to load in each chunk

        Yields:
            Chunks of pandas DataFrame containing the market data
        """
        try:
            # Check if the data file exists
            file_path = os.path.join(self.DATA_PARQUET_LOCATION, f"{symbol}.parquet")
            if not os.path.exists(file_path):
                # If parquet file doesn't exist, try to download or convert from pickle
                try:
                    # Try to load from pickle and convert to parquet
                    pickle_path = os.path.join(self.DATA_PICKLE_LOCATION, f"{symbol}.pkl.gz")
                    if os.path.exists(pickle_path):
                        df = pd.read_pickle(pickle_path)
                        self._save_data_parquet(symbol, df)
                        logger.info(f"Converted pickle data for {symbol} to parquet format")
                    else:
                        # Download data if neither format exists
                        logger.info(f"Data for {symbol} not found locally. Downloading from Alpha Vantage...")
                        df = await self._download_and_save_data(symbol)
                        logger.info(f"Downloaded and saved data for {symbol}")
                except Exception as e:
                    logger.error(f"Error preparing data for chunked reading: {str(e)}")
                    raise DataProcessingError(f"Error preparing data for chunked reading: {str(e)}") from e

            # Use pandas to read the parquet file in chunks
            # Since parquet doesn't support native chunking like CSV, we'll use filters to simulate chunks
            # First, get all dates in the range
            try:
                # Read just the index to get all dates
                df_index = pd.read_parquet(file_path, columns=[])
                df_index.index = pd.to_datetime(df_index.index).date

                # Filter to the requested date range
                mask = (df_index.index >= start_date) & (df_index.index <= end_date)
                dates_in_range = df_index.index[mask].sort_values()

                # If no dates in range, return empty DataFrame
                if len(dates_in_range) == 0:
                    logger.warning(f"No data found for {symbol} between {start_date} and {end_date}")
                    yield pd.DataFrame()
                    return

                # Process dates in chunks
                for i in range(0, len(dates_in_range), chunk_size):
                    chunk_dates = dates_in_range[i:i+chunk_size]
                    if len(chunk_dates) == 0:
                        break

                    # Create filters for this chunk of dates
                    min_date = chunk_dates.min()
                    max_date = chunk_dates.max()

                    # Load just this chunk of data
                    filters = [
                        ('date', '>=', min_date),
                        ('date', '<=', max_date)
                    ]
                    chunk_df = self._load_data(symbol, filters=filters)

                    # Yield this chunk
                    yield chunk_df

                    # Clear memory
                    del chunk_df

            except Exception as e:
                logger.error(f"Error reading data in chunks: {str(e)}")
                raise DataProcessingError(f"Error reading data in chunks: {str(e)}") from e

        except Exception as e:
            logger.error(f"Unexpected error in chunked data reading: {str(e)}")
            raise DataProcessingError(f"Unexpected error in chunked data reading: {str(e)}") from e

    async def get_data(self, symbol: str, start_date: date, end_date: date, chunk_size: int = None) -> pd.DataFrame:
        """
        Get market data for a symbol within a specified date range.

        This method handles loading data from local storage or downloading it if necessary.
        It also updates existing data if the requested end date is more recent than the
        available data. Results are cached for improved performance.

        Args:
            symbol: Stock symbol (e.g., 'MSFT', 'AAPL')
            start_date: Start date for the data range
            end_date: End date for the data range
            chunk_size: If provided, returns a generator that yields chunks of data
                       instead of loading the entire dataset into memory

        Returns:
            A pandas DataFrame containing the market data for the specified date range,
            or a generator yielding chunks of data if chunk_size is provided

        Raises:
            DataNotFoundError: If data cannot be found or downloaded
            DataProcessingError: If there's an error processing the data
        """
        # If chunk_size is provided, use the chunked version
        if chunk_size is not None:
            return self._get_data_chunked(symbol, start_date, end_date, chunk_size)

        # Generate cache key
        cache_key = self._get_data_cache_key(symbol, start_date, end_date)

        # Check if data is in cache
        if cache_key in self._data_cache:
            logger.debug(f"Cache hit for {symbol} from {start_date} to {end_date}")
            return self._data_cache[cache_key]

        # Not in cache, get the data
        logger.debug(f"Cache miss for {symbol} from {start_date} to {end_date}")
        result = await self._get_data_uncached(symbol, start_date, end_date)

        # Store in cache
        self._data_cache[cache_key] = result
        logger.debug(f"Cached data for {symbol} from {start_date} to {end_date}")

        return result

    async def get_mean(self, symbol: str, start_date: date, end_date: date, field_name: str) -> float:
        """
        Calculate the mean value of a specific field over a date range.

        Args:
            symbol: Stock symbol (e.g., 'MSFT', 'AAPL')
            start_date: Start date for the calculation
            end_date: End date for the calculation
            field_name: The field to calculate the mean for (e.g., 'open', 'close')

        Returns:
            The mean value of the specified field over the date range

        Raises:
            DataNotFoundError: If data cannot be found or downloaded
            DataProcessingError: If there's an error processing the data
        """
        field = FieldName(field_name)
        df = await self.get_data(symbol, start_date, end_date)

        return df[field.value].mean()

    async def get_sma(self, symbol: str, current_date: date, number_of_days: int, field_name: str) -> float:
        """
        Calculate the Simple Moving Average (SMA) for a specific field.

        Args:
            symbol: Stock symbol (e.g., 'MSFT', 'AAPL')
            current_date: The end date for the SMA calculation
            number_of_days: The number of days to include in the SMA calculation
            field_name: The field to calculate the SMA for (e.g., 'open', 'close')

        Returns:
            The Simple Moving Average value

        Raises:
            DataNotFoundError: If data cannot be found or downloaded
            DataProcessingError: If there's an error processing the data
        """
        field = FieldName(field_name)
        start_date = current_date - timedelta(days=number_of_days)
        df = await self.get_data(symbol, start_date, current_date)
        return df[field.value].mean()

    async def get_value(self, symbol: str, for_date: date, for_field: FieldName) -> float:
        """
        Get the value of a specific field for a specific date.

        Args:
            symbol: Stock symbol (e.g., 'MSFT', 'AAPL')
            for_date: The date to get the value for
            for_field: The field to get the value for (FieldName enum)

        Returns:
            The value of the specified field on the specified date, or None if no data exists

        Raises:
            DataNotFoundError: If data cannot be found or downloaded
            DataProcessingError: If there's an error processing the data
        """
        d = await self.get_data(symbol=symbol, start_date=for_date, end_date=for_date)
        if d.size == 0:
            return None
        return d.loc[for_date, for_field.value]


if __name__ == '__main__':
    async def main():
        reader = DataReader()
        # data = reader._load_data("MSFT")
        # data = await reader.get_data(symbol="MSFT", start_date="2024-03-01", end_date="2024-04-01")
        # print(data)
        # data = await reader.get_data(symbol="MSFT", start_date="2024-03-01", end_date="2024-04-01")
        # data = await reader.get_mean("MSFT", "2024-03-01", "2024-04-01", FieldName.OPEN.value)

        # data = await reader.get_data(symbol="MSFT", start_date=date(2024, 3, 1), end_date=date(2024, 4, 1))
        # print(data)
        # data = await reader.get_data(symbol="MSFT", start_date=date(2024, 3, 1), end_date=date(2024, 3, 1))
        data = await reader.get_value(symbol="MSFT", for_date=date(2024, 4, 29), for_field=FieldName.CLOSE)

        logger.debug(f"Data type: {type(data)}")
        logger.debug(f"Data value: {data}")

    asyncio.run(main())
