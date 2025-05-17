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

    async def get_data_with_lookback(self, symbol, start_date, end_date, lookback_days):
        """
        Get data for a symbol with an extended lookback period.

        Args:
            symbol (str): The stock symbol.
            start_date: The start date for the analysis.
            end_date: The end date for the analysis.
            lookback_days (int): Number of days to look back for calculations.

        Returns:
            pd.DataFrame: DataFrame with price data.
        """
        extended_start_date = start_date - timedelta(days=lookback_days)
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

class MomentumStrategy(BaseStrategy, IndicatorMixin):
    """Base class for momentum trading strategies."""

    async def generate_signals(self, symbol, start_date, end_date):
        """
        Generate trading signals for the given symbol and date range.
        
        This implementation should be overridden by subclasses with specific momentum strategies.

        Args:
            symbol (str): The stock symbol.
            start_date: The start date for the analysis.
            end_date: The end date for the analysis.

        Returns:
            pd.DataFrame: DataFrame with dates as index and signals as values.
        """
        raise NotImplementedError("Subclasses must implement this method")