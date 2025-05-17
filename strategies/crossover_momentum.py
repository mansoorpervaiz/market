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

from strategies.base_strategy import MomentumStrategy, Signal
from interfaces.data_access.data_reader_interface import DataReaderInterface

class CrossoverMomentumStrategy(MomentumStrategy):
    """
    Crossover Momentum strategy.

    Combines multiple timeframe moving average crossovers with momentum indicators
    and volume confirmation for a robust trading strategy.

    Features:
    1. Multiple timeframe moving average crossovers (short, medium, long)
    2. RSI momentum filter
    3. Volume confirmation
    4. Trend strength filter
    """

    def __init__(self, data_reader: DataReaderInterface, 
                 short_window=10, medium_window=30, long_window=50,
                 rsi_period=14, rsi_oversold=30, rsi_overbought=70,
                 volume_threshold=1.5, trend_strength_period=20):
        """
        Initialize the Crossover Momentum strategy.

        Args:
            data_reader: An instance of a class implementing DataReaderInterface.
            short_window (int): Window for the short-term moving average.
            medium_window (int): Window for the medium-term moving average.
            long_window (int): Window for the long-term moving average.
            rsi_period (int): Period for RSI calculation.
            rsi_oversold (int): RSI threshold for oversold condition.
            rsi_overbought (int): RSI threshold for overbought condition.
            volume_threshold (float): Volume multiple above average for confirmation.
            trend_strength_period (int): Period for trend strength calculation.
        """
        super().__init__(data_reader)
        self.short_window = short_window
        self.medium_window = medium_window
        self.long_window = long_window
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.volume_threshold = volume_threshold
        self.trend_strength_period = trend_strength_period

    async def generate_signals(self, symbol, start_date, end_date):
        """
        Generate buy/sell signals based on Crossover Momentum strategy.

        Args:
            symbol (str): The stock symbol.
            start_date: The start date for the analysis.
            end_date: The end date for the analysis.

        Returns:
            pd.DataFrame: DataFrame with dates as index and signals as values.
        """
        # Get data with lookback period
        lookback_days = max(self.long_window, self.rsi_period, self.trend_strength_period) * 3
        df = await self.get_data_with_lookback(symbol, start_date, end_date, lookback_days)

        if df.empty:
            return df

        # Prepare data by calculating all necessary indicators
        df = self._prepare_data(df)

        # Generate buy and sell signals
        df = self._generate_buy_signals(df)
        df = self._generate_sell_signals(df)

        # Filter to the requested date range and include debug columns
        columns_to_return = ['signal', 'short_ma', 'medium_ma', 'long_ma', 'rsi', 'volume_ratio', 'trend_strength']

        return self.filter_to_date_range(df, start_date, columns_to_return)

    def _prepare_data(self, df):
        """
        Prepare data by calculating all necessary indicators.

        Args:
            df (pd.DataFrame): DataFrame with price data.

        Returns:
            pd.DataFrame: DataFrame with calculated indicators.
        """
        # Calculate moving averages
        df = self.calculate_moving_averages(df, [self.short_window, self.medium_window, self.long_window])

        # Rename columns to match the original implementation
        df.rename(columns={
            f'ma_{self.short_window}': 'short_ma',
            f'ma_{self.medium_window}': 'medium_ma',
            f'ma_{self.long_window}': 'long_ma'
        }, inplace=True)

        # Calculate RSI
        df = self.calculate_rsi(df, self.rsi_period)

        # Calculate volume ratio
        df = self.calculate_volume_ratio(df, 20)

        # Calculate trend strength (using standard deviation of returns)
        df['returns'] = df['close'].pct_change()
        df['trend_strength'] = df['returns'].rolling(window=self.trend_strength_period).std() * np.sqrt(252)  # Annualized

        # Initialize signal column
        df['signal'] = Signal.HOLD.value

        return df

    def _generate_buy_signals(self, df):
        """
        Generate buy signals based on multiple conditions.

        Args:
            df (pd.DataFrame): DataFrame with calculated indicators.

        Returns:
            pd.DataFrame: DataFrame with buy signals applied.
        """
        # 1. Short MA crosses above Medium MA
        short_above_medium = (df['short_ma'] > df['medium_ma']) & (df['short_ma'].shift(1) <= df['medium_ma'].shift(1))

        # 2. Medium MA crosses above Long MA (stronger signal)
        medium_above_long = (df['medium_ma'] > df['long_ma']) & (df['medium_ma'].shift(1) <= df['long_ma'].shift(1))

        # 3. All MAs are aligned (short > medium > long) - strongest signal
        all_aligned = (df['short_ma'] > df['medium_ma']) & (df['medium_ma'] > df['long_ma'])

        # 4. RSI conditions
        rsi_bullish = df['rsi'] > self.rsi_oversold
        rsi_not_overbought = df['rsi'] < self.rsi_overbought

        # 5. Volume confirmation
        volume_confirmed = df['volume_ratio'] > self.volume_threshold

        # Combine signals with different strengths
        # Strong buy: All aligned + RSI bullish + Volume confirmed
        strong_buy = all_aligned & rsi_bullish & volume_confirmed

        # Medium buy: Medium crosses above Long + RSI bullish
        medium_buy = medium_above_long & rsi_bullish & rsi_not_overbought

        # Weak buy: Short crosses above Medium + RSI not overbought
        weak_buy = short_above_medium & rsi_not_overbought

        # Apply buy signals
        df.loc[strong_buy, 'signal'] = Signal.BUY.value
        df.loc[medium_buy & ~strong_buy, 'signal'] = Signal.BUY.value
        df.loc[weak_buy & ~medium_buy & ~strong_buy, 'signal'] = Signal.BUY.value

        return df

    def _generate_sell_signals(self, df):
        """
        Generate sell signals based on multiple conditions.

        Args:
            df (pd.DataFrame): DataFrame with calculated indicators.

        Returns:
            pd.DataFrame: DataFrame with sell signals applied.
        """
        # 1. Short MA crosses below Medium MA
        short_below_medium = (df['short_ma'] < df['medium_ma']) & (df['short_ma'].shift(1) >= df['medium_ma'].shift(1))

        # 2. RSI overbought
        rsi_overbought = df['rsi'] > self.rsi_overbought

        # 3. Trend weakening (decreasing trend strength)
        trend_weakening = df['trend_strength'] < df['trend_strength'].shift(1)

        # Combine sell signals
        sell_signal = short_below_medium | (rsi_overbought & trend_weakening)

        # Apply sell signals
        df.loc[sell_signal, 'signal'] = Signal.SELL.value

        return df
