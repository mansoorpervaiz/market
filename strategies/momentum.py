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

from strategies.base_strategy import BaseStrategy, IndicatorMixin, Signal, MomentumStrategy
from interfaces.data_access.data_reader_interface import DataReaderInterface


class RateOfChangeStrategy(MomentumStrategy):
    """
    Rate of Change (ROC) strategy.
    Buy when the price has increased more than X% over the past N days.
    """

    def __init__(self, data_reader: DataReaderInterface, n_days=14, threshold_pct=5, sell_threshold_pct=-3):
        """
        Initialize the ROC strategy.

        Args:
            data_reader: An instance of a class implementing DataReaderInterface.
            n_days (int): Number of days to calculate ROC over.
            threshold_pct (float): Percentage threshold for buy signals.
            sell_threshold_pct (float): Percentage threshold for sell signals.
        """
        super().__init__(data_reader)
        self.n_days = n_days
        self.threshold_pct = threshold_pct
        self.sell_threshold_pct = sell_threshold_pct
        # Store previous close prices for chunked processing
        self.previous_closes = []

    async def generate_signals(self, symbol: str, start_date: date, end_date: date, chunk_size=None) -> pd.DataFrame:
        """
        Generate buy/sell signals based on Rate of Change.

        Args:
            symbol: The stock symbol (e.g., 'MSFT', 'AAPL')
            start_date: The start date for the analysis
            end_date: The end date for the analysis
            chunk_size: If provided, process data in chunks of this size to reduce memory usage

        Returns:
            A pandas DataFrame with dates as index and signals as values,
            or a generator yielding chunks if chunk_size is provided

        Raises:
            DataNotFoundError: If data cannot be found or downloaded
            DataProcessingError: If there's an error processing the data
        """
        # Reset state for chunked processing
        self.previous_closes = []

        # If chunk_size is provided, use chunked processing
        if chunk_size is not None:
            lookback_days = self.n_days * 2
            return await self.generate_signals_chunked(symbol, start_date, end_date, chunk_size, lookback_days)

        # Traditional processing (load all data at once)
        lookback_days = self.n_days * 2
        df = await self.get_data_with_lookback(symbol, start_date, end_date, lookback_days)

        if df.empty:
            return df

        # Prepare data by calculating Rate of Change
        df = self._prepare_data(df)

        # Generate signals
        df = self._generate_signals(df)

        # Filter to the requested date range
        return self.filter_to_date_range(df, start_date, ['signal'])

    def _prepare_data_chunk(self, chunk):
        """
        Prepare a chunk of data by calculating Rate of Change.

        Args:
            chunk (pd.DataFrame): DataFrame chunk with price data.

        Returns:
            pd.DataFrame: DataFrame chunk with calculated indicators.
        """
        # For ROC calculation across chunks, we need to maintain a history of close prices
        if len(self.previous_closes) >= self.n_days:
            # We have enough history to calculate ROC for this chunk
            # Combine previous closes with current chunk closes
            all_closes = self.previous_closes[-self.n_days:] + chunk['close'].tolist()

            # Calculate ROC for each row in the chunk
            for i in range(len(chunk)):
                if i + self.n_days < len(all_closes):
                    old_price = all_closes[i]
                    new_price = all_closes[i + self.n_days]
                    if old_price > 0:  # Avoid division by zero
                        roc = ((new_price - old_price) / old_price) * 100
                        chunk.loc[chunk.index[i], 'roc'] = roc
        else:
            # Not enough history yet, calculate what we can
            chunk.loc[:, 'roc'] = np.nan

            # If we have some history, calculate ROC for the rows we can
            if self.previous_closes:
                combined_closes = self.previous_closes + chunk['close'].tolist()
                for i in range(len(chunk)):
                    idx = len(self.previous_closes) + i
                    if idx >= self.n_days:
                        old_price = combined_closes[idx - self.n_days]
                        new_price = combined_closes[idx]
                        if old_price > 0:  # Avoid division by zero
                            roc = ((new_price - old_price) / old_price) * 100
                            chunk.loc[chunk.index[i], 'roc'] = roc

        # Update our history for the next chunk
        self.previous_closes.extend(chunk['close'].tolist())
        # Keep only what we need
        self.previous_closes = self.previous_closes[-self.n_days*2:]

        # Initialize signal column
        chunk.loc[:, 'signal'] = Signal.HOLD.value

        return chunk

    def _generate_signals_chunk(self, chunk):
        """
        Generate signals for a chunk of data.

        Args:
            chunk (pd.DataFrame): DataFrame chunk with calculated indicators.

        Returns:
            pd.DataFrame: DataFrame chunk with signals applied.
        """
        # Generate buy signals
        chunk = self._generate_buy_signals(chunk)

        # Generate sell signals
        chunk = self._generate_sell_signals(chunk)

        return chunk

    def _prepare_data(self, df):
        """
        Prepare data by calculating Rate of Change.

        Args:
            df (pd.DataFrame): DataFrame with price data.

        Returns:
            pd.DataFrame: DataFrame with Rate of Change calculated.
        """
        # Calculate Rate of Change
        df.loc[:, 'roc'] = df['close'].pct_change(self.n_days) * 100

        # Initialize signal column
        df.loc[:, 'signal'] = Signal.HOLD.value

        return df

    def _generate_signals(self, df):
        """
        Generate buy and sell signals based on Rate of Change thresholds.

        Args:
            df (pd.DataFrame): DataFrame with Rate of Change calculated.

        Returns:
            pd.DataFrame: DataFrame with signals applied.
        """
        # Generate buy signals
        df = self._generate_buy_signals(df)

        # Generate sell signals
        df = self._generate_sell_signals(df)

        return df

    def _generate_buy_signals(self, df):
        """
        Generate buy signals when ROC exceeds the buy threshold.

        Args:
            df (pd.DataFrame): DataFrame with Rate of Change calculated.

        Returns:
            pd.DataFrame: DataFrame with buy signals applied.
        """
        # Buy when ROC exceeds threshold
        df.loc[df['roc'] >= self.threshold_pct, 'signal'] = Signal.BUY.value

        return df

    def _generate_sell_signals(self, df):
        """
        Generate sell signals when ROC falls below the sell threshold.

        Args:
            df (pd.DataFrame): DataFrame with Rate of Change calculated.

        Returns:
            pd.DataFrame: DataFrame with sell signals applied.
        """
        # Sell when ROC falls below sell threshold
        df.loc[df['roc'] <= self.sell_threshold_pct, 'signal'] = Signal.SELL.value

        return df


class MovingAverageCrossoverStrategy(MomentumStrategy):
    """
    Moving Average Crossover strategy.
    Buy when a short-term moving average crosses above a long-term moving average.
    """

    def __init__(self, data_reader: DataReaderInterface, short_window=20, long_window=50):
        """
        Initialize the Moving Average Crossover strategy.

        Args:
            data_reader: An instance of a class implementing DataReaderInterface.
            short_window (int): Window for the short-term moving average.
            long_window (int): Window for the long-term moving average.
        """
        super().__init__(data_reader)
        self.short_window = short_window
        self.long_window = long_window

    async def generate_signals(self, symbol: str, start_date: date, end_date: date, chunk_size=None) -> pd.DataFrame:
        """
        Generate buy/sell signals based on Moving Average Crossover.

        Args:
            symbol: The stock symbol (e.g., 'MSFT', 'AAPL')
            start_date: The start date for the analysis
            end_date: The end date for the analysis
            chunk_size: If provided, process data in chunks of this size to reduce memory usage

        Returns:
            A pandas DataFrame with dates as index and signals as values,
            or a generator yielding chunks if chunk_size is provided

        Raises:
            DataNotFoundError: If data cannot be found or downloaded
            DataProcessingError: If there's an error processing the data
        """
        # If chunk_size is provided, use chunked processing
        if chunk_size is not None:
            lookback_days = self.long_window * 2
            return await self.generate_signals_chunked(symbol, start_date, end_date, chunk_size, lookback_days)

        # Traditional processing (load all data at once)
        lookback_days = self.long_window * 2
        df = await self.get_data_with_lookback(symbol, start_date, end_date, lookback_days)

        if df.empty:
            return df

        # Prepare data by calculating moving averages
        df = self._prepare_data(df)

        # Generate signals
        df = self._generate_signals(df)

        # Filter to the requested date range
        return self.filter_to_date_range(df, start_date, ['signal'])

    def _prepare_data_chunk(self, chunk):
        """
        Prepare a chunk of data by calculating moving averages.

        Args:
            chunk (pd.DataFrame): DataFrame chunk with price data.

        Returns:
            pd.DataFrame: DataFrame chunk with calculated indicators.
        """
        # Calculate moving averages for this chunk
        # Note: The calculate_moving_averages_chunked method is used by generate_signals_chunked
        # to maintain state between chunks, so we use the regular version here
        chunk = self.calculate_moving_averages(chunk, [self.short_window, self.long_window])

        # Rename columns to match the original implementation
        chunk.rename(columns={
            f'ma_{self.short_window}': 'short_ma',
            f'ma_{self.long_window}': 'long_ma'
        }, inplace=True)

        # Initialize signal column
        chunk.loc[:, 'signal'] = Signal.HOLD.value

        return chunk

    def _generate_signals_chunk(self, chunk):
        """
        Generate signals for a chunk of data.

        Args:
            chunk (pd.DataFrame): DataFrame chunk with calculated indicators.

        Returns:
            pd.DataFrame: DataFrame chunk with signals applied.
        """
        # Generate buy signals
        chunk = self._generate_buy_signals(chunk)

        # Generate sell signals
        chunk = self._generate_sell_signals(chunk)

        return chunk

    def _prepare_data(self, df):
        """
        Prepare data by calculating moving averages.

        Args:
            df (pd.DataFrame): DataFrame with price data.

        Returns:
            pd.DataFrame: DataFrame with calculated moving averages.
        """
        # Calculate moving averages
        df = self.calculate_moving_averages(df, [self.short_window, self.long_window])

        # Rename columns to match the original implementation
        df.rename(columns={
            f'ma_{self.short_window}': 'short_ma',
            f'ma_{self.long_window}': 'long_ma'
        }, inplace=True)

        # Initialize signal column
        df.loc[:, 'signal'] = Signal.HOLD.value

        return df

    def _generate_signals(self, df):
        """
        Generate buy and sell signals based on moving average crossovers.

        Args:
            df (pd.DataFrame): DataFrame with calculated moving averages.

        Returns:
            pd.DataFrame: DataFrame with signals applied.
        """
        # Generate buy signals
        df = self._generate_buy_signals(df)

        # Generate sell signals
        df = self._generate_sell_signals(df)

        return df

    def _generate_buy_signals(self, df):
        """
        Generate buy signals when short MA crosses above long MA.

        Args:
            df (pd.DataFrame): DataFrame with calculated moving averages.

        Returns:
            pd.DataFrame: DataFrame with buy signals applied.
        """
        # Buy when short MA crosses above long MA
        buy_condition = (df['short_ma'] > df['long_ma']) & (df['short_ma'].shift(1) <= df['long_ma'].shift(1))
        df.loc[buy_condition, 'signal'] = Signal.BUY.value

        return df

    def _generate_sell_signals(self, df):
        """
        Generate sell signals when short MA crosses below long MA.

        Args:
            df (pd.DataFrame): DataFrame with calculated moving averages.

        Returns:
            pd.DataFrame: DataFrame with sell signals applied.
        """
        # Sell when short MA crosses below long MA
        sell_condition = (df['short_ma'] < df['long_ma']) & (df['short_ma'].shift(1) >= df['long_ma'].shift(1))
        df.loc[sell_condition, 'signal'] = Signal.SELL.value

        return df


class BreakoutStrategy(MomentumStrategy):
    """
    Enhanced Breakout strategy.
    Buy when price breaks 20-day high with volatility filter, volume confirmation, and trend filter.
    Exit using tighter stop-loss or trailing exit logic instead of waiting for 10-day low.
    """

    def __init__(self, data_reader: DataReaderInterface, high_period=20, low_period=10, 
                 use_volatility_filter=True, atr_period=14, atr_threshold=1.0,
                 use_volume_confirmation=True, volume_threshold=1.2,
                 use_trailing_stop=True, trailing_stop_pct=2.0,
                 use_trend_filter=True, ma_period=100):
        """
        Initialize the enhanced Breakout strategy.

        Args:
            data_reader: An instance of a class implementing DataReaderInterface.
            high_period (int): Period for calculating the high price (default: 20 days).
            low_period (int): Period for calculating the low price (default: 10 days).
            use_volatility_filter (bool): Whether to use ATR volatility filter.
            atr_period (int): Period for ATR calculation.
            atr_threshold (float): Minimum ATR multiple to consider market volatile enough.
            use_volume_confirmation (bool): Whether to require volume confirmation.
            volume_threshold (float): Volume multiple above average to confirm breakout.
            use_trailing_stop (bool): Whether to use trailing stop for exits.
            trailing_stop_pct (float): Percentage below recent high for trailing stop.
            use_trend_filter (bool): Whether to only trade in uptrends.
            ma_period (int): Period for moving average trend filter.
        """
        super().__init__(data_reader)
        self.high_period = high_period
        self.low_period = low_period
        self.use_volatility_filter = use_volatility_filter
        self.atr_period = atr_period
        self.atr_threshold = atr_threshold
        self.use_volume_confirmation = use_volume_confirmation
        self.volume_threshold = volume_threshold
        self.use_trailing_stop = use_trailing_stop
        self.trailing_stop_pct = trailing_stop_pct
        self.use_trend_filter = use_trend_filter
        self.ma_period = ma_period

        # State variables for chunked processing
        self.high_values = []
        self.low_values = []
        self.close_values = []
        self.volume_values = []
        self.tr_values = []
        self.position_state = 0
        self.highest_since_buy = None
        self.trailing_stop = None
        self.prev_high_20d = None
        self.prev_low_10d = None
        self.prev_close = None

    async def generate_signals(self, symbol: str, start_date: date, end_date: date, chunk_size=None) -> pd.DataFrame:
        """
        Generate buy/sell signals based on price breakouts with enhanced filters.

        This strategy identifies breakouts above recent highs and applies multiple filters
        including volatility, volume confirmation, and trend analysis to improve signal quality.

        Args:
            symbol: The stock symbol (e.g., 'MSFT', 'AAPL')
            start_date: The start date for the analysis
            end_date: The end date for the analysis
            chunk_size: If provided, process data in chunks of this size to reduce memory usage

        Returns:
            A pandas DataFrame with dates as index and signals as values, along with
            additional columns for strategy components (high/low levels, ATR, volume ratio, etc.),
            or a generator yielding chunks if chunk_size is provided

        Raises:
            DataNotFoundError: If data cannot be found or downloaded
            DataProcessingError: If there's an error processing the data
        """
        # Reset state for chunked processing
        self.high_values = []
        self.low_values = []
        self.close_values = []
        self.volume_values = []
        self.tr_values = []
        self.position_state = 0
        self.highest_since_buy = None
        self.trailing_stop = None
        self.prev_high_20d = None
        self.prev_low_10d = None
        self.prev_close = None

        # If chunk_size is provided, use chunked processing
        if chunk_size is not None:
            # Need more historical data for the rolling calculations
            lookback_days = max(self.high_period, self.low_period, self.atr_period, self.ma_period) * 2
            return await self.generate_signals_chunked(symbol, start_date, end_date, chunk_size, lookback_days)

        # Traditional processing (load all data at once)
        from datetime import timedelta

        # Need more historical data for the rolling calculations
        lookback_days = max(self.high_period, self.low_period, self.atr_period, self.ma_period) * 2
        extended_start_date = start_date - timedelta(days=lookback_days)

        # Get price data
        df = await self.data_reader.get_data(symbol, extended_start_date, end_date)

        # Check for empty dataframe
        if df.empty:
            return pd.DataFrame(index=pd.date_range(start_date, end_date), columns=['signal']).fillna(Signal.HOLD.value)

        # Create a copy of the DataFrame to avoid SettingWithCopyWarning
        df = df.copy()

        # Prepare data by calculating all necessary indicators
        df = self._prepare_data(df)

        # Generate buy signals
        df = self._generate_buy_signals(df)

        # Generate sell signals
        df = self._generate_sell_signals(df)

        # Filter to the requested date range and include debug columns
        columns_to_return = self._get_columns_to_return()

        result = df.loc[df.index >= start_date, columns_to_return]
        return result

    def _prepare_data_chunk(self, chunk):
        """
        Prepare a chunk of data by calculating all necessary indicators.

        Args:
            chunk (pd.DataFrame): DataFrame chunk with price data.

        Returns:
            pd.DataFrame: DataFrame chunk with calculated indicators.
        """
        # Store values for rolling calculations
        self.high_values.extend(chunk['high'].tolist())
        self.low_values.extend(chunk['low'].tolist())
        self.close_values.extend(chunk['close'].tolist())
        self.volume_values.extend(chunk['volume'].tolist())

        # Keep only what we need
        self.high_values = self.high_values[-self.high_period*2:]
        self.low_values = self.low_values[-self.low_period*2:]
        self.close_values = self.close_values[-self.ma_period*2:]
        self.volume_values = self.volume_values[-20*2:]  # 20 is hardcoded for volume average

        # Calculate rolling high and low
        for i in range(len(chunk)):
            # Calculate high_20d
            idx_high = len(self.high_values) - len(chunk) + i
            if idx_high >= self.high_period:
                window_high = self.high_values[idx_high - self.high_period:idx_high]
                chunk.loc[chunk.index[i], 'high_20d'] = max(window_high)
            else:
                chunk.loc[chunk.index[i], 'high_20d'] = np.nan

            # Calculate low_10d
            idx_low = len(self.low_values) - len(chunk) + i
            if idx_low >= self.low_period:
                window_low = self.low_values[idx_low - self.low_period:idx_low]
                chunk.loc[chunk.index[i], 'low_10d'] = min(window_low)
            else:
                chunk.loc[chunk.index[i], 'low_10d'] = np.nan

        # Calculate ATR for volatility filter
        if self.use_volatility_filter:
            chunk = self._calculate_atr_chunk(chunk)

        # Calculate volume average for confirmation
        if self.use_volume_confirmation:
            for i in range(len(chunk)):
                idx_vol = len(self.volume_values) - len(chunk) + i
                if idx_vol >= 20:
                    window_vol = self.volume_values[idx_vol - 20:idx_vol]
                    chunk.loc[chunk.index[i], 'volume_avg'] = sum(window_vol) / len(window_vol)
                    chunk.loc[chunk.index[i], 'volume_ratio'] = chunk['volume'].iloc[i] / chunk.loc[chunk.index[i], 'volume_avg']
                else:
                    chunk.loc[chunk.index[i], 'volume_avg'] = np.nan
                    chunk.loc[chunk.index[i], 'volume_ratio'] = np.nan

        # Calculate moving average for trend filter
        if self.use_trend_filter:
            for i in range(len(chunk)):
                idx_ma = len(self.close_values) - len(chunk) + i
                if idx_ma >= self.ma_period:
                    window_ma = self.close_values[idx_ma - self.ma_period:idx_ma]
                    chunk.loc[chunk.index[i], 'ma_100d'] = sum(window_ma) / len(window_ma)
                else:
                    chunk.loc[chunk.index[i], 'ma_100d'] = np.nan

        # Initialize signal column
        chunk.loc[:, 'signal'] = Signal.HOLD.value

        # Initialize position tracking columns if using trailing stop
        if self.use_trailing_stop:
            chunk.loc[:, 'position_state'] = 0
            chunk.loc[:, 'highest_since_buy'] = np.nan
            chunk.loc[:, 'trailing_stop'] = np.nan

            # Update position state based on previous state
            if self.position_state == 1:
                chunk.loc[:, 'position_state'] = 1
                chunk.loc[:, 'highest_since_buy'] = self.highest_since_buy
                chunk.loc[:, 'trailing_stop'] = self.trailing_stop

        return chunk

    def _calculate_atr_chunk(self, chunk):
        """
        Calculate Average True Range (ATR) for a chunk.

        Args:
            chunk (pd.DataFrame): DataFrame chunk with price data.

        Returns:
            pd.DataFrame: DataFrame chunk with ATR calculations added.
        """
        # Calculate True Range
        for i in range(len(chunk)):
            if i == 0 and self.prev_close is not None:
                # First row in chunk, use previous close from last chunk
                tr = max(
                    chunk['high'].iloc[i] - chunk['low'].iloc[i],
                    abs(chunk['high'].iloc[i] - self.prev_close),
                    abs(chunk['low'].iloc[i] - self.prev_close)
                )
            elif i > 0:
                # Use previous row in this chunk
                tr = max(
                    chunk['high'].iloc[i] - chunk['low'].iloc[i],
                    abs(chunk['high'].iloc[i] - chunk['close'].iloc[i-1]),
                    abs(chunk['low'].iloc[i] - chunk['close'].iloc[i-1])
                )
            else:
                # First row in first chunk, just use high-low
                tr = chunk['high'].iloc[i] - chunk['low'].iloc[i]

            chunk.loc[chunk.index[i], 'tr'] = tr
            self.tr_values.append(tr)

        # Keep only what we need
        self.tr_values = self.tr_values[-self.atr_period*2:]

        # Calculate ATR
        for i in range(len(chunk)):
            idx_atr = len(self.tr_values) - len(chunk) + i
            if idx_atr >= self.atr_period:
                window_tr = self.tr_values[idx_atr - self.atr_period:idx_atr]
                chunk.loc[chunk.index[i], 'atr'] = sum(window_tr) / len(window_tr)
                chunk.loc[chunk.index[i], 'atr_ratio'] = chunk.loc[chunk.index[i], 'atr'] / chunk['close'].iloc[i] * 100
            else:
                chunk.loc[chunk.index[i], 'atr'] = np.nan
                chunk.loc[chunk.index[i], 'atr_ratio'] = np.nan

        # Update prev_close for next chunk
        if not chunk.empty:
            self.prev_close = chunk['close'].iloc[-1]

        return chunk

    def _generate_signals_chunk(self, chunk):
        """
        Generate signals for a chunk of data.

        Args:
            chunk (pd.DataFrame): DataFrame chunk with calculated indicators.

        Returns:
            pd.DataFrame: DataFrame chunk with signals applied.
        """
        # Store previous values for comparison
        self.prev_high_20d = chunk['high_20d'].iloc[-1] if not chunk.empty else self.prev_high_20d
        self.prev_low_10d = chunk['low_10d'].iloc[-1] if not chunk.empty else self.prev_low_10d

        # Generate buy signals
        chunk = self._generate_buy_signals_chunk(chunk)

        # Generate sell signals
        chunk = self._generate_sell_signals_chunk(chunk)

        # Update position state for next chunk
        if not chunk.empty:
            self.position_state = chunk['position_state'].iloc[-1]
            if self.position_state == 1:
                self.highest_since_buy = chunk['highest_since_buy'].iloc[-1]
                self.trailing_stop = chunk['trailing_stop'].iloc[-1]
            else:
                self.highest_since_buy = None
                self.trailing_stop = None

        return chunk

    def _generate_buy_signals_chunk(self, chunk):
        """
        Generate buy signals for a chunk based on breakout conditions and filters.

        Args:
            chunk (pd.DataFrame): DataFrame chunk with calculated indicators.

        Returns:
            pd.DataFrame: DataFrame chunk with buy signals applied.
        """
        for i in range(len(chunk)):
            # Skip if we don't have enough data yet
            if pd.isna(chunk['high_20d'].iloc[i]):
                continue

            # Buy condition: price breaks above the high_period high
            if i == 0:
                # First row in chunk, compare with previous high from last chunk
                buy_condition = self.prev_high_20d is not None and chunk['close'].iloc[i] > self.prev_high_20d
            else:
                # Compare with previous row in this chunk
                buy_condition = chunk['close'].iloc[i] > chunk['high_20d'].iloc[i-1]

            # Apply volatility filter
            if self.use_volatility_filter and not pd.isna(chunk['atr_ratio'].iloc[i]):
                buy_condition = buy_condition and (chunk['atr_ratio'].iloc[i] > self.atr_threshold)

            # Apply volume confirmation
            if self.use_volume_confirmation and not pd.isna(chunk['volume_ratio'].iloc[i]):
                buy_condition = buy_condition and (chunk['volume_ratio'].iloc[i] > self.volume_threshold)

            # Apply trend filter
            if self.use_trend_filter and not pd.isna(chunk['ma_100d'].iloc[i]):
                buy_condition = buy_condition and (chunk['close'].iloc[i] > chunk['ma_100d'].iloc[i])

            # Apply buy signal
            if buy_condition:
                chunk.loc[chunk.index[i], 'signal'] = Signal.BUY.value

        return chunk

    def _generate_sell_signals_chunk(self, chunk):
        """
        Generate sell signals for a chunk based on trailing stop or traditional breakout conditions.

        Args:
            chunk (pd.DataFrame): DataFrame chunk with calculated indicators.

        Returns:
            pd.DataFrame: DataFrame chunk with sell signals applied.
        """
        if self.use_trailing_stop:
            # Process position state and trailing stop
            for i in range(len(chunk)):
                # Get previous state (either from previous row or from instance variable)
                if i == 0:
                    prev_position_state = self.position_state
                else:
                    prev_position_state = chunk['position_state'].iloc[i-1]

                # Get current signal
                if i == 0:
                    current_signal = Signal.HOLD.value  # Default for first row
                else:
                    current_signal = chunk['signal'].iloc[i-1]

                # Update position state based on previous signal
                if current_signal == Signal.BUY.value:
                    # Enter position
                    chunk.loc[chunk.index[i], 'position_state'] = 1
                    chunk.loc[chunk.index[i], 'highest_since_buy'] = chunk['close'].iloc[i]
                    chunk.loc[chunk.index[i], 'trailing_stop'] = chunk['close'].iloc[i] * (1 - self.trailing_stop_pct/100)
                elif current_signal == Signal.SELL.value:
                    # Exit position
                    chunk.loc[chunk.index[i], 'position_state'] = 0
                    # Reset tracking variables
                    chunk.loc[chunk.index[i], 'highest_since_buy'] = np.nan
                    chunk.loc[chunk.index[i], 'trailing_stop'] = np.nan
                else:
                    # Maintain previous state
                    chunk.loc[chunk.index[i], 'position_state'] = prev_position_state

                    # If in position, update highest price and trailing stop
                    if prev_position_state == 1:
                        # Get previous highest
                        if i == 0:
                            prev_highest = self.highest_since_buy
                        else:
                            prev_highest = chunk['highest_since_buy'].iloc[i-1]

                        # Update highest price since buy
                        current_price = chunk['close'].iloc[i]
                        new_highest = max(prev_highest, current_price) if not np.isnan(prev_highest) else current_price
                        chunk.loc[chunk.index[i], 'highest_since_buy'] = new_highest

                        # Update trailing stop
                        chunk.loc[chunk.index[i], 'trailing_stop'] = new_highest * (1 - self.trailing_stop_pct/100)

            # Generate sell signals based on trailing stop (only when in position)
            trailing_stop_condition = (chunk['position_state'] == 1) & (chunk['close'] < chunk['trailing_stop'])
            chunk.loc[trailing_stop_condition, 'signal'] = Signal.SELL.value
        else:
            # Traditional sell when price breaks below the low_period low
            for i in range(len(chunk)):
                # Skip if we don't have enough data yet
                if pd.isna(chunk['low_10d'].iloc[i]):
                    continue

                # Sell condition: price breaks below the low_period low
                if i == 0:
                    # First row in chunk, compare with previous low from last chunk
                    sell_condition = self.prev_low_10d is not None and chunk['close'].iloc[i] < self.prev_low_10d
                else:
                    # Compare with previous row in this chunk
                    sell_condition = chunk['close'].iloc[i] < chunk['low_10d'].iloc[i-1]

                # Apply sell signal
                if sell_condition:
                    chunk.loc[chunk.index[i], 'signal'] = Signal.SELL.value

        return chunk

    def _prepare_data(self, df):
        """
        Prepare data by calculating all necessary indicators.

        Args:
            df (pd.DataFrame): DataFrame with price data.

        Returns:
            pd.DataFrame: DataFrame with calculated indicators.
        """
        # Calculate rolling high and low
        df.loc[:, 'high_20d'] = df['high'].rolling(window=self.high_period).max()
        df.loc[:, 'low_10d'] = df['low'].rolling(window=self.low_period).min()

        # Calculate ATR for volatility filter
        if self.use_volatility_filter:
            df = self._calculate_atr(df)

        # Calculate volume average for confirmation
        if self.use_volume_confirmation:
            df.loc[:, 'volume_avg'] = df['volume'].rolling(window=20).mean()
            df.loc[:, 'volume_ratio'] = df['volume'] / df['volume_avg']

        # Calculate moving average for trend filter
        if self.use_trend_filter:
            df.loc[:, 'ma_100d'] = df['close'].rolling(window=self.ma_period).mean()

        # Initialize signal column
        df.loc[:, 'signal'] = Signal.HOLD.value

        return df

    def _calculate_atr(self, df):
        """
        Calculate Average True Range (ATR) for volatility filtering.

        Args:
            df (pd.DataFrame): DataFrame with price data.

        Returns:
            pd.DataFrame: DataFrame with ATR calculations added.
        """
        df.loc[:, 'tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df.loc[:, 'atr'] = df['tr'].rolling(window=self.atr_period).mean()
        df.loc[:, 'atr_ratio'] = df['atr'] / df['close'] * 100  # ATR as percentage of price

        return df

    def _generate_buy_signals(self, df):
        """
        Generate buy signals based on breakout conditions and filters.

        Args:
            df (pd.DataFrame): DataFrame with calculated indicators.

        Returns:
            pd.DataFrame: DataFrame with buy signals applied.
        """
        # Buy condition: price breaks above the high_period high
        buy_condition = (df['close'] > df['high_20d'].shift(1))

        # Apply volatility filter
        if self.use_volatility_filter:
            buy_condition = buy_condition & (df['atr_ratio'] > self.atr_threshold)

        # Apply volume confirmation
        if self.use_volume_confirmation:
            buy_condition = buy_condition & (df['volume_ratio'] > self.volume_threshold)

        # Apply trend filter
        if self.use_trend_filter:
            buy_condition = buy_condition & (df['close'] > df['ma_100d'])

        # Apply buy signals
        df.loc[buy_condition, 'signal'] = Signal.BUY.value

        return df

    def _generate_sell_signals(self, df):
        """
        Generate sell signals based on trailing stop or traditional breakout conditions.

        Args:
            df (pd.DataFrame): DataFrame with calculated indicators.

        Returns:
            pd.DataFrame: DataFrame with sell signals applied.
        """
        if self.use_trailing_stop:
            df = self._apply_trailing_stop(df)
        else:
            # Traditional sell when price breaks below the low_period low
            sell_condition = (df['close'] < df['low_10d'].shift(1))
            df.loc[sell_condition, 'signal'] = Signal.SELL.value

        return df

    def _apply_trailing_stop(self, df):
        """
        Apply trailing stop logic for position management and sell signals.

        Args:
            df (pd.DataFrame): DataFrame with calculated indicators.

        Returns:
            pd.DataFrame: DataFrame with trailing stop logic applied.
        """
        # Initialize position tracking columns with vectorized operations
        df.loc[:, 'position_state'] = 0  # 0: not in position, 1: in position
        df.loc[:, 'highest_since_buy'] = np.nan
        df.loc[:, 'trailing_stop'] = np.nan

        # Process signals and update position state
        for i in range(1, len(df)):
            # Get previous state
            prev_position_state = df.iloc[i-1]['position_state']
            current_signal = df.iloc[i-1]['signal']

            # Update position state based on previous signal
            if current_signal == Signal.BUY.value:
                # Enter position
                df.iloc[i, df.columns.get_loc('position_state')] = 1
                df.iloc[i, df.columns.get_loc('highest_since_buy')] = df.iloc[i]['close']
                df.iloc[i, df.columns.get_loc('trailing_stop')] = df.iloc[i]['close'] * (1 - self.trailing_stop_pct/100)
            elif current_signal == Signal.SELL.value:
                # Exit position
                df.iloc[i, df.columns.get_loc('position_state')] = 0
                # Reset tracking variables
                df.iloc[i, df.columns.get_loc('highest_since_buy')] = np.nan
                df.iloc[i, df.columns.get_loc('trailing_stop')] = np.nan
            else:
                # Maintain previous state
                df.iloc[i, df.columns.get_loc('position_state')] = prev_position_state

                # If in position, update highest price and trailing stop
                if prev_position_state == 1:
                    df = self._update_trailing_stop(df, i)

        # Generate sell signals based on trailing stop (only when in position)
        trailing_stop_condition = (df['position_state'] == 1) & (df['close'] < df['trailing_stop'])
        df.loc[trailing_stop_condition, 'signal'] = Signal.SELL.value

        return df

    def _update_trailing_stop(self, df, i):
        """
        Update trailing stop values based on current price.

        Args:
            df (pd.DataFrame): DataFrame with position tracking.
            i (int): Current index in the DataFrame.

        Returns:
            pd.DataFrame: DataFrame with updated trailing stop values.
        """
        # Update highest price since buy
        prev_highest = df.iloc[i-1]['highest_since_buy']
        current_price = df.iloc[i]['close']
        new_highest = max(prev_highest, current_price) if not np.isnan(prev_highest) else current_price
        df.iloc[i, df.columns.get_loc('highest_since_buy')] = new_highest

        # Update trailing stop
        df.iloc[i, df.columns.get_loc('trailing_stop')] = new_highest * (1 - self.trailing_stop_pct/100)

        return df

    def _get_columns_to_return(self):
        """
        Get the list of columns to include in the result DataFrame.

        Returns:
            list: List of column names to include in the result.
        """
        columns_to_return = ['signal', 'high_20d', 'low_10d']

        # Add debug columns based on enabled features
        if self.use_volatility_filter:
            columns_to_return.extend(['atr', 'atr_ratio'])
        if self.use_volume_confirmation:
            columns_to_return.extend(['volume_ratio'])
        if self.use_trend_filter:
            columns_to_return.append('ma_100d')
        if self.use_trailing_stop:
            columns_to_return.extend(['highest_since_buy', 'trailing_stop', 'position_state'])

        return columns_to_return


class RSIStrategy(MomentumStrategy):
    """
    Relative Strength Index (RSI) strategy.
    Buy when RSI crosses above 30 (oversold), sell when it crosses below 70 (overbought).
    With trend filter option: only take RSI signals when price > 200-day moving average.
    """

    def __init__(self, data_reader: DataReaderInterface, window=14, oversold=30, overbought=70, use_trend_filter=True, ma_period=200):
        """
        Initialize the RSI strategy.

        Args:
            data_reader: An instance of a class implementing DataReaderInterface.
            window (int): Window for RSI calculation.
            oversold (int): Threshold for oversold condition.
            overbought (int): Threshold for overbought condition.
            use_trend_filter (bool): Whether to use trend filter (price > MA).
            ma_period (int): Period for the moving average used in trend filter.
        """
        super().__init__(data_reader)
        self.window = window
        self.oversold = oversold
        self.overbought = overbought
        self.use_trend_filter = use_trend_filter
        self.ma_period = ma_period

        # State variables for chunked processing
        self.last_close = None
        self.last_avg_gain = None
        self.last_avg_loss = None
        self.ma_values = []

    async def generate_signals(self, symbol: str, start_date: date, end_date: date, chunk_size=None) -> pd.DataFrame:
        """
        Generate buy/sell signals based on RSI (Relative Strength Index).

        This strategy generates buy signals when RSI crosses above the oversold threshold
        and sell signals when RSI crosses below the overbought threshold. An optional
        trend filter can be applied to only take buy signals when price is above a moving average.

        Args:
            symbol: The stock symbol (e.g., 'MSFT', 'AAPL')
            start_date: The start date for the analysis
            end_date: The end date for the analysis
            chunk_size: If provided, process data in chunks of this size to reduce memory usage

        Returns:
            A pandas DataFrame with dates as index and signals as values, along with
            the RSI values and moving average values if trend filter is enabled,
            or a generator yielding chunks if chunk_size is provided

        Raises:
            DataNotFoundError: If data cannot be found or downloaded
            DataProcessingError: If there's an error processing the data
        """
        # Reset state for chunked processing
        self.last_close = None
        self.last_avg_gain = None
        self.last_avg_loss = None
        self.ma_values = []

        # If chunk_size is provided, use chunked processing
        if chunk_size is not None:
            lookback_days = self._calculate_lookback_days()
            return await self.generate_signals_chunked(symbol, start_date, end_date, chunk_size, lookback_days)

        # Traditional processing (load all data at once)
        lookback_days = self._calculate_lookback_days()
        df = await self.get_data_with_lookback(symbol, start_date, end_date, lookback_days)

        if df.empty:
            return df

        # Prepare data by calculating indicators
        df = self._prepare_data(df)

        if df['rsi'].isna().all():
            return pd.DataFrame(index=pd.date_range(start_date, end_date), columns=['signal']).fillna(Signal.HOLD.value)

        # Generate signals
        df = self._generate_signals(df)

        # Filter to the requested date range and include debug columns
        columns_to_return = self._get_columns_to_return(df)

        return self.filter_to_date_range(df, start_date, columns_to_return)

    def _prepare_data_chunk(self, chunk):
        """
        Prepare a chunk of data by calculating RSI and moving average if needed.

        Args:
            chunk (pd.DataFrame): DataFrame chunk with price data.

        Returns:
            pd.DataFrame: DataFrame chunk with calculated indicators.
        """
        # Calculate RSI for this chunk, maintaining state between chunks
        chunk = self._calculate_rsi_chunk(chunk)

        # Calculate moving average for trend filter if enabled
        if self.use_trend_filter:
            chunk = self._calculate_ma_chunk(chunk)

        # Initialize signal column
        chunk.loc[:, 'signal'] = Signal.HOLD.value

        return chunk

    def _calculate_rsi_chunk(self, chunk):
        """
        Calculate RSI for a chunk, maintaining state between chunks.

        Args:
            chunk (pd.DataFrame): DataFrame chunk with price data.

        Returns:
            pd.DataFrame: DataFrame chunk with RSI calculated.
        """
        # Calculate price change
        if self.last_close is not None:
            # Calculate first price change using the last value from previous chunk
            first_change = chunk['close'].iloc[0] - self.last_close
            # Calculate rest of the changes within the chunk
            rest_changes = chunk['close'].diff().iloc[1:]
            # Combine them
            chunk['price_change'] = pd.concat([pd.Series([first_change], index=[chunk.index[0]]), rest_changes])
        else:
            chunk['price_change'] = chunk['close'].diff()

        # Calculate gains and losses
        chunk['gain'] = chunk['price_change'].clip(lower=0)
        chunk['loss'] = -chunk['price_change'].clip(upper=0)

        # Calculate average gain and loss
        if self.last_avg_gain is not None and self.last_avg_loss is not None:
            # Use previous values for continuity
            for i in range(len(chunk)):
                if i == 0:
                    # First row uses the last values from previous chunk
                    avg_gain = (self.last_avg_gain * (self.window - 1) + chunk['gain'].iloc[i]) / self.window
                    avg_loss = (self.last_avg_loss * (self.window - 1) + chunk['loss'].iloc[i]) / self.window
                else:
                    # Rest use the previous row in this chunk
                    avg_gain = (chunk['avg_gain'].iloc[i-1] * (self.window - 1) + chunk['gain'].iloc[i]) / self.window
                    avg_loss = (chunk['avg_loss'].iloc[i-1] * (self.window - 1) + chunk['loss'].iloc[i]) / self.window

                chunk.loc[chunk.index[i], 'avg_gain'] = avg_gain
                chunk.loc[chunk.index[i], 'avg_loss'] = avg_loss
        else:
            # First chunk, calculate normally
            chunk['avg_gain'] = chunk['gain'].ewm(alpha=1/self.window, min_periods=self.window).mean()
            chunk['avg_loss'] = chunk['loss'].ewm(alpha=1/self.window, min_periods=self.window).mean()

        # Calculate RS and RSI
        chunk['rs'] = chunk['avg_gain'] / chunk['avg_loss']
        chunk['rsi'] = 100 - (100 / (1 + chunk['rs']))

        # Update state for next chunk
        if not chunk.empty:
            self.last_close = chunk['close'].iloc[-1]
            self.last_avg_gain = chunk['avg_gain'].iloc[-1]
            self.last_avg_loss = chunk['avg_loss'].iloc[-1]

        return chunk

    def _calculate_ma_chunk(self, chunk):
        """
        Calculate moving average for a chunk, maintaining state between chunks.

        Args:
            chunk (pd.DataFrame): DataFrame chunk with price data.

        Returns:
            pd.DataFrame: DataFrame chunk with moving average calculated.
        """
        # Add current chunk's close prices to our history
        self.ma_values.extend(chunk['close'].tolist())

        # Keep only what we need
        self.ma_values = self.ma_values[-self.ma_period:]

        # Calculate MA for each row in the chunk
        for i in range(len(chunk)):
            # Get the relevant window of prices for this row
            idx = len(self.ma_values) - len(chunk) + i
            if idx >= self.ma_period:
                # We have enough history to calculate a full MA
                window = self.ma_values[idx - self.ma_period:idx]
                chunk.loc[chunk.index[i], 'ma'] = sum(window) / len(window)
            else:
                # Not enough history yet
                chunk.loc[chunk.index[i], 'ma'] = np.nan

        return chunk

    def _generate_signals_chunk(self, chunk):
        """
        Generate signals for a chunk of data.

        Args:
            chunk (pd.DataFrame): DataFrame chunk with calculated indicators.

        Returns:
            pd.DataFrame: DataFrame chunk with signals applied.
        """
        # Skip if RSI is all NaN
        if chunk['rsi'].isna().all():
            return chunk

        # Generate buy signals
        chunk = self._generate_buy_signals(chunk)

        # Generate sell signals
        chunk = self._generate_sell_signals(chunk)

        return chunk

    def _calculate_lookback_days(self):
        """
        Calculate the required lookback days for data retrieval.

        Returns:
            int: Number of days to look back for data retrieval.
        """
        lookback_days = self.window * 3
        if self.use_trend_filter:
            # Need more historical data for the moving average calculation
            lookback_days = max(lookback_days, self.ma_period * 2)
        return lookback_days

    def _prepare_data(self, df):
        """
        Prepare data by calculating RSI and moving average if needed.

        Args:
            df (pd.DataFrame): DataFrame with price data.

        Returns:
            pd.DataFrame: DataFrame with calculated indicators.
        """
        # Calculate RSI
        df = self.calculate_rsi(df, self.window)

        # Calculate moving average for trend filter if enabled
        if self.use_trend_filter:
            df = self.calculate_moving_averages(df, [self.ma_period])
            df.rename(columns={f'ma_{self.ma_period}': 'ma'}, inplace=True)

        # Initialize signal column
        df.loc[:, 'signal'] = Signal.HOLD.value

        return df

    def _generate_signals(self, df):
        """
        Generate buy and sell signals based on RSI conditions.

        Args:
            df (pd.DataFrame): DataFrame with calculated indicators.

        Returns:
            pd.DataFrame: DataFrame with signals applied.
        """
        # Generate buy signals
        df = self._generate_buy_signals(df)

        # Generate sell signals
        df = self._generate_sell_signals(df)

        return df

    def _generate_buy_signals(self, df):
        """
        Generate buy signals based on RSI crossing above oversold threshold.

        Args:
            df (pd.DataFrame): DataFrame with calculated indicators.

        Returns:
            pd.DataFrame: DataFrame with buy signals applied.
        """
        # Buy when RSI crosses above oversold threshold
        buy_condition = (df['rsi'] > self.oversold) & (df['rsi'].shift(1) <= self.oversold)

        # Add trend filter condition if enabled
        if self.use_trend_filter:
            # Only buy when price is above the moving average
            buy_condition = buy_condition & (df['close'] > df['ma'])

        df.loc[buy_condition, 'signal'] = Signal.BUY.value

        return df

    def _generate_sell_signals(self, df):
        """
        Generate sell signals based on RSI crossing below overbought threshold.

        Args:
            df (pd.DataFrame): DataFrame with calculated indicators.

        Returns:
            pd.DataFrame: DataFrame with sell signals applied.
        """
        # Sell when RSI crosses below overbought threshold
        sell_condition = (df['rsi'] < self.overbought) & (df['rsi'].shift(1) >= self.overbought)
        df.loc[sell_condition, 'signal'] = Signal.SELL.value

        return df

    def _get_columns_to_return(self, df):
        """
        Get the list of columns to include in the result DataFrame.

        Args:
            df (pd.DataFrame): DataFrame with calculated indicators.

        Returns:
            list: List of column names to include in the result.
        """
        columns_to_return = ['signal', 'rsi']
        if self.use_trend_filter and 'ma' in df.columns:
            columns_to_return.append('ma')

        return columns_to_return
