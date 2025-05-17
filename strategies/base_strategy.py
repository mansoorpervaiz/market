# Copyright (c) 2025 Mansoor Pervaiz
# All rights reserved.
#
# This file is part of a proprietary software project.
# Unauthorized copying, distribution, modification, or use of this file,
# via any medium, is strictly prohibited unless explicit permission is granted
# by the author.
#
# For licensing inquiries, contact: mansoorpervaizdev@gmail.com

import pandas as pd
import numpy as np
from datetime import timedelta
from enum import Enum
from abc import ABC, abstractmethod

from interfaces.business_logic.strategy_interface import StrategyInterface
from interfaces.data_access.data_reader_interface import DataReaderInterface

class Signal(Enum):
    """Enum for trading signals."""
    BUY = 1
    SELL = -1
    HOLD = 0

class BaseStrategy(StrategyInterface, ABC):
    """Base class for all trading strategies."""

    def __init__(self, data_reader: DataReaderInterface):
        """
        Initialize the strategy with a data reader.

        Args:
            data_reader: An instance of a class implementing DataReaderInterface to access financial data.
        """
        self.data_reader = data_reader

    @abstractmethod
    async def generate_signals(self, symbol, start_date, end_date):
        """
        Generate trading signals for the given symbol and date range.

        Args:
            symbol (str): The stock symbol.
            start_date: The start date for the analysis.
            end_date: The end date for the analysis.

        Returns:
            pd.DataFrame: DataFrame with dates as index and signals as values.
        """
        pass

    async def get_data_with_lookback(self, symbol, start_date, end_date, lookback_days, chunk_size=None):
        """
        Get data for a symbol with an extended lookback period.

        Args:
            symbol (str): The stock symbol.
            start_date: The start date for the analysis.
            end_date: The end date for the analysis.
            lookback_days (int): Number of days to look back for calculations.
            chunk_size (int, optional): If provided, process data in chunks of this size.

        Returns:
            pd.DataFrame: DataFrame with price data, or a generator if chunk_size is provided.
        """
        extended_start_date = start_date - timedelta(days=lookback_days)

        if chunk_size is not None:
            # Return a generator that processes data in chunks
            return self.data_reader.get_data(symbol, extended_start_date, end_date, chunk_size=chunk_size)
        else:
            # Get all data at once (traditional approach)
            df = await self.data_reader.get_data(symbol, extended_start_date, end_date)

            # Check for empty dataframe
            if df.empty:
                return pd.DataFrame(index=pd.date_range(start_date, end_date), columns=['signal']).fillna(Signal.HOLD.value)

            # Create a copy of the DataFrame to avoid SettingWithCopyWarning
            return df.copy()

    def filter_to_date_range(self, df, start_date, columns_to_return):
        """
        Filter DataFrame to the requested date range and columns.

        Args:
            df (pd.DataFrame): DataFrame to filter.
            start_date: The start date for the analysis.
            columns_to_return (list): List of columns to include in the result.

        Returns:
            pd.DataFrame: Filtered DataFrame.
        """
        return df.loc[df.index >= start_date, columns_to_return]

class IndicatorMixin:
    """Mixin class with common indicator calculations."""

    def calculate_moving_averages(self, df, windows):
        """
        Calculate moving averages for the given windows.

        Args:
            df (pd.DataFrame): DataFrame with price data.
            windows (list): List of window sizes for moving averages.

        Returns:
            pd.DataFrame: DataFrame with moving averages added.
        """
        for window in windows:
            df[f'ma_{window}'] = df['close'].rolling(window=window).mean()
        return df

    def calculate_moving_averages_chunked(self, chunks, windows, min_periods=None):
        """
        Calculate moving averages for the given windows using chunked data.

        This method processes data in chunks to avoid loading the entire dataset into memory.

        Args:
            chunks: Iterator or generator yielding DataFrame chunks.
            windows (list): List of window sizes for moving averages.
            min_periods (int, optional): Minimum number of observations required for calculation.

        Returns:
            Generator yielding DataFrame chunks with moving averages added.
        """
        # Initialize state for each window
        window_states = {window: [] for window in windows}

        for chunk in chunks:
            if chunk.empty:
                yield chunk
                continue

            # Process each window
            for window in windows:
                # Calculate moving average for this chunk
                if len(window_states[window]) > 0:
                    # Combine previous values with current chunk for proper calculation
                    combined_values = pd.concat([pd.Series(window_states[window]), chunk['close']])
                    ma_values = combined_values.rolling(window=window, min_periods=min_periods or 1).mean()

                    # Extract only the values for the current chunk
                    chunk[f'ma_{window}'] = ma_values.iloc[-len(chunk):].values
                else:
                    # First chunk, calculate normally
                    chunk[f'ma_{window}'] = chunk['close'].rolling(window=window, min_periods=min_periods or 1).mean()

                # Update state with the last window-sized values
                window_states[window] = chunk['close'].iloc[-window:].tolist()

            yield chunk

    def calculate_rsi(self, df, period=14):
        """
        Calculate Relative Strength Index (RSI).

        Args:
            df (pd.DataFrame): DataFrame with price data.
            period (int): Period for RSI calculation.

        Returns:
            pd.DataFrame: DataFrame with RSI added.
        """
        df['price_change'] = df['close'].diff()
        df['gain'] = df['price_change'].clip(lower=0)
        df['loss'] = -df['price_change'].clip(upper=0)

        # Calculate average gain and loss using Wilder's smoothing
        df['avg_gain'] = df['gain'].ewm(alpha=1/period, min_periods=period).mean()
        df['avg_loss'] = df['loss'].ewm(alpha=1/period, min_periods=period).mean()

        # Calculate RS and RSI
        df['rs'] = df['avg_gain'] / df['avg_loss']
        df['rsi'] = 100 - (100 / (1 + df['rs']))

        return df

    def calculate_rsi_chunked(self, chunks, period=14):
        """
        Calculate Relative Strength Index (RSI) using chunked data.

        This method processes data in chunks to avoid loading the entire dataset into memory.

        Args:
            chunks: Iterator or generator yielding DataFrame chunks.
            period (int): Period for RSI calculation.

        Returns:
            Generator yielding DataFrame chunks with RSI added.
        """
        # Initialize state variables
        last_close = None
        last_avg_gain = None
        last_avg_loss = None

        for chunk in chunks:
            if chunk.empty:
                yield chunk
                continue

            # Calculate price change
            if last_close is not None:
                # Calculate first price change using the last value from previous chunk
                first_change = chunk['close'].iloc[0] - last_close
                # Calculate rest of the changes within the chunk
                rest_changes = chunk['close'].diff().iloc[1:]
                # Combine them
                chunk['price_change'] = pd.concat([pd.Series([first_change]), rest_changes])
            else:
                chunk['price_change'] = chunk['close'].diff()

            # Calculate gains and losses
            chunk['gain'] = chunk['price_change'].clip(lower=0)
            chunk['loss'] = -chunk['price_change'].clip(upper=0)

            # Calculate average gain and loss
            if last_avg_gain is not None and last_avg_loss is not None:
                # Use previous values for continuity
                for i in range(len(chunk)):
                    if i == 0:
                        # First row uses the last values from previous chunk
                        avg_gain = (last_avg_gain * (period - 1) + chunk['gain'].iloc[i]) / period
                        avg_loss = (last_avg_loss * (period - 1) + chunk['loss'].iloc[i]) / period
                    else:
                        # Rest use the previous row in this chunk
                        avg_gain = (chunk['avg_gain'].iloc[i-1] * (period - 1) + chunk['gain'].iloc[i]) / period
                        avg_loss = (chunk['avg_loss'].iloc[i-1] * (period - 1) + chunk['loss'].iloc[i]) / period

                    chunk.loc[chunk.index[i], 'avg_gain'] = avg_gain
                    chunk.loc[chunk.index[i], 'avg_loss'] = avg_loss
            else:
                # First chunk, calculate normally
                chunk['avg_gain'] = chunk['gain'].ewm(alpha=1/period, min_periods=period).mean()
                chunk['avg_loss'] = chunk['loss'].ewm(alpha=1/period, min_periods=period).mean()

            # Calculate RS and RSI
            chunk['rs'] = chunk['avg_gain'] / chunk['avg_loss']
            chunk['rsi'] = 100 - (100 / (1 + chunk['rs']))

            # Update state for next chunk
            last_close = chunk['close'].iloc[-1]
            last_avg_gain = chunk['avg_gain'].iloc[-1]
            last_avg_loss = chunk['avg_loss'].iloc[-1]

            yield chunk

    def calculate_volume_ratio(self, df, period=20):
        """
        Calculate volume ratio compared to average.

        Args:
            df (pd.DataFrame): DataFrame with price data.
            period (int): Period for volume average calculation.

        Returns:
            pd.DataFrame: DataFrame with volume ratio added.
        """
        df['volume_avg'] = df['volume'].rolling(window=period).mean()
        df['volume_ratio'] = df['volume'] / df['volume_avg']
        return df

    def calculate_volume_ratio_chunked(self, chunks, period=20):
        """
        Calculate volume ratio compared to average using chunked data.

        This method processes data in chunks to avoid loading the entire dataset into memory.

        Args:
            chunks: Iterator or generator yielding DataFrame chunks.
            period (int): Period for volume average calculation.

        Returns:
            Generator yielding DataFrame chunks with volume ratio added.
        """
        # Initialize state with previous volume values
        volume_history = []

        for chunk in chunks:
            if chunk.empty:
                yield chunk
                continue

            # Combine previous values with current chunk for proper calculation
            if volume_history:
                combined_volume = pd.concat([pd.Series(volume_history), chunk['volume']])
                volume_avg = combined_volume.rolling(window=period).mean()

                # Extract only the values for the current chunk
                chunk['volume_avg'] = volume_avg.iloc[-len(chunk):].values
            else:
                # First chunk, calculate normally
                chunk['volume_avg'] = chunk['volume'].rolling(window=period).mean()

            # Calculate volume ratio
            chunk['volume_ratio'] = chunk['volume'] / chunk['volume_avg']

            # Update state with the last period-sized values
            volume_history = chunk['volume'].iloc[-period:].tolist()

            yield chunk

class MomentumStrategy(BaseStrategy, IndicatorMixin):
    """Base class for momentum trading strategies."""

    async def generate_signals(self, symbol, start_date, end_date, chunk_size=None):
        """
        Generate trading signals for the given symbol and date range.

        This implementation should be overridden by subclasses with specific momentum strategies.

        Args:
            symbol (str): The stock symbol.
            start_date: The start date for the analysis.
            end_date: The end date for the analysis.
            chunk_size (int, optional): If provided, process data in chunks of this size.

        Returns:
            pd.DataFrame: DataFrame with dates as index and signals as values,
                         or a generator yielding chunks if chunk_size is provided.
        """
        raise NotImplementedError("Subclasses must implement this method")

    async def generate_signals_chunked(self, symbol, start_date, end_date, chunk_size, lookback_days):
        """
        Generate trading signals in chunks to reduce memory usage.

        This is a helper method that subclasses can use to implement chunked processing.

        Args:
            symbol (str): The stock symbol.
            start_date: The start date for the analysis.
            end_date: The end date for the analysis.
            chunk_size (int): Size of each chunk to process.
            lookback_days (int): Number of days to look back for calculations.

        Returns:
            Generator yielding DataFrame chunks with signals.
        """
        # Get data in chunks with lookback period
        extended_start_date = start_date - timedelta(days=lookback_days)
        data_chunks = await self.get_data_with_lookback(symbol, extended_start_date, end_date, chunk_size=chunk_size)

        # Process each chunk
        for chunk in data_chunks:
            if chunk.empty:
                yield pd.DataFrame(index=pd.date_range(start_date, end_date), columns=['signal']).fillna(Signal.HOLD.value)
                continue

            # Prepare data and generate signals for this chunk
            # Subclasses should implement _prepare_data_chunk and _generate_signals_chunk
            chunk = self._prepare_data_chunk(chunk)
            chunk = self._generate_signals_chunk(chunk)

            # Filter to the requested date range
            chunk = chunk.loc[chunk.index >= start_date]

            yield chunk

    def _prepare_data_chunk(self, chunk):
        """
        Prepare a chunk of data by calculating necessary indicators.

        This method should be overridden by subclasses.

        Args:
            chunk (pd.DataFrame): DataFrame chunk with price data.

        Returns:
            pd.DataFrame: DataFrame chunk with calculated indicators.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def _generate_signals_chunk(self, chunk):
        """
        Generate signals for a chunk of data.

        This method should be overridden by subclasses.

        Args:
            chunk (pd.DataFrame): DataFrame chunk with calculated indicators.

        Returns:
            pd.DataFrame: DataFrame chunk with signals applied.
        """
        raise NotImplementedError("Subclasses must implement this method")
