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
import os
from datetime import datetime, timedelta, date
from enum import Enum

from strategies.base_strategy import MomentumStrategy, Signal
from data_manager.symbol_manager import SymbolManager

class RankingCriteria(Enum):
    """Enum for different ranking criteria."""
    PERCENT_ABOVE_AVERAGE = 1
    VOLUME_VS_AVERAGE = 2
    COMBINED_SCORE = 3

class PositionSizeMethod(Enum):
    """Enum for different position sizing methods."""
    EQUAL_WEIGHT = 1
    VOLATILITY_ADJUSTED = 2
    PERFORMANCE_BASED = 3

class TopBreakoutStrategy(MomentumStrategy):
    """
    Top Breakout strategy.
    Selects the top 10% breakout stocks each week ranked by:
    - % above 20-day average
    - Volume vs. average
    - Combined score
    """

    def __init__(self, data_reader, symbols_file="data/SP500.csv", 
                 avg_period=20, top_percent=10, 
                 ranking_criteria=RankingCriteria.COMBINED_SCORE,
                 rebalance_days=7,
                 use_trailing_stop=True, trailing_stop_pct=2.0,
                 position_size_method=PositionSizeMethod.EQUAL_WEIGHT,
                 use_volatility_filter=True, atr_period=14, max_atr_ratio=5.0):
        """
        Initialize the Top Breakout strategy.

        Args:
            data_reader: An instance of DataReader.
            symbols_file (str): Path to the CSV file containing symbols.
            avg_period (int): Period for calculating the average price (default: 20 days).
            top_percent (int): Percentage of top stocks to select (default: 10%).
            ranking_criteria (RankingCriteria): Criteria for ranking stocks.
            rebalance_days (int): Number of days between rebalancing (default: 7 days).
            use_trailing_stop (bool): Whether to use trailing stop for exits (default: True).
            trailing_stop_pct (float): Percentage below recent high for trailing stop (default: 2.0%).
            position_size_method (PositionSizeMethod): Method for position sizing (default: EQUAL_WEIGHT).
            use_volatility_filter (bool): Whether to filter out excessively volatile stocks (default: True).
            atr_period (int): Period for ATR calculation (default: 14 days).
            max_atr_ratio (float): Maximum ATR ratio allowed (as percentage of price) (default: 5.0%).
        """
        super().__init__(data_reader)
        self.symbols_file = symbols_file
        self.avg_period = avg_period
        self.top_percent = top_percent
        self.ranking_criteria = ranking_criteria
        self.rebalance_days = rebalance_days
        self.position_size_method = position_size_method

        # Volatility filter parameters
        self.use_volatility_filter = use_volatility_filter
        self.atr_period = atr_period
        self.max_atr_ratio = max_atr_ratio

        # Check if the symbols file exists, if not create it (for SP500.csv)
        if not os.path.exists(symbols_file) and symbols_file == "data/SP500.csv":
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(symbols_file), exist_ok=True)
            # Import fetch_sp500_tickers function if it's not already imported
            try:
                from example_momentum_trading import fetch_sp500_tickers
                # Fetch and save S&P 500 tickers
                fetch_sp500_tickers(symbols_file)
                print(f"Created symbols file: {symbols_file}")
            except ImportError:
                print(f"Warning: Could not import fetch_sp500_tickers function. The symbols file {symbols_file} may not be created.")

        self.symbol_manager = SymbolManager(symbols_file)
        self.selected_symbols = []
        self.last_rebalance_date = None

        # Trailing stop parameters
        self.use_trailing_stop = use_trailing_stop
        self.trailing_stop_pct = trailing_stop_pct

        # Position tracking for trailing stop
        self.position_states = {}  # Dictionary to track position state for each symbol
        self.highest_since_buy = {}  # Dictionary to track highest price since buy for each symbol
        self.trailing_stops = {}  # Dictionary to track trailing stop levels for each symbol

        # Position sizing
        self.position_sizes = {}  # Dictionary to track position size for each symbol

    async def _calculate_metrics(self, symbols, current_date):
        """
        Calculate metrics for each symbol.

        Args:
            symbols (list): List of symbols to analyze.
            current_date (datetime.date): Current date for analysis.

        Returns:
            pd.DataFrame: DataFrame with metrics for each symbol.
        """
        # Calculate start date for data retrieval
        start_date = current_date - timedelta(days=self.avg_period * 2)

        metrics = []

        for symbol in symbols:
            try:
                # Get data with lookback period
                df = await self.get_data_with_lookback(symbol, start_date, current_date, self.avg_period * 2)

                if df.empty:
                    continue

                # Calculate moving averages for price
                df = self.calculate_moving_averages(df, [self.avg_period])
                df.rename(columns={f'ma_{self.avg_period}': 'avg_price'}, inplace=True)

                # Calculate volume ratio
                df = self.calculate_volume_ratio(df, self.avg_period)

                # Get the latest data point
                latest = df.iloc[-1]

                # Calculate metrics
                pct_above_avg = (latest['close'] / latest['avg_price'] - 1) * 100
                volume_ratio = latest['volume_ratio']

                # Calculate combined score (equal weighting)
                combined_score = (pct_above_avg + volume_ratio) / 2

                # Calculate ATR (Average True Range) for volatility filtering
                atr_ratio = None
                if self.use_volatility_filter:
                    # Calculate True Range
                    df['tr'] = np.maximum(
                        df['high'] - df['low'],
                        np.maximum(
                            abs(df['high'] - df['close'].shift(1)),
                            abs(df['low'] - df['close'].shift(1))
                        )
                    )
                    # Calculate ATR
                    df['atr'] = df['tr'].rolling(window=self.atr_period).mean()
                    # Calculate ATR ratio as percentage of price
                    df['atr_ratio'] = df['atr'] / df['close'] * 100

                    # Get the latest ATR ratio
                    # Check if 'atr_ratio' is in the latest row and is not NaN
                    latest_atr_ratio = df['atr_ratio'].iloc[-1]
                    if not pd.isna(latest_atr_ratio):
                        atr_ratio = latest_atr_ratio

                # Calculate volatility (standard deviation of returns) if needed for position sizing
                volatility = None
                if self.position_size_method == PositionSizeMethod.VOLATILITY_ADJUSTED:
                    # Calculate daily returns
                    df['returns'] = df['close'].pct_change()
                    # Calculate volatility as standard deviation of returns
                    volatility = df['returns'].std() * 100  # Convert to percentage

                # Add to metrics list
                metrics_dict = {
                    'symbol': symbol,
                    'pct_above_avg': pct_above_avg,
                    'volume_ratio': volume_ratio,
                    'combined_score': combined_score,
                    'close': latest['close'],
                    'volume': latest['volume']
                }

                # Add ATR ratio if calculated
                if atr_ratio is not None:
                    metrics_dict['atr_ratio'] = atr_ratio

                # Add volatility if calculated
                if volatility is not None:
                    metrics_dict['volatility'] = volatility

                metrics.append(metrics_dict)

            except Exception as e:
                print(f"Error processing {symbol}: {e}")
                continue

        # Convert to DataFrame
        metrics_df = pd.DataFrame(metrics)

        return metrics_df

    async def _select_top_symbols(self, current_date):
        """
        Select the top symbols based on the ranking criteria and calculate position sizes.

        Args:
            current_date (datetime.date): Current date for analysis.

        Returns:
            list: List of selected symbols.
        """
        # Get all symbols
        symbols = self.symbol_manager.get_symbols_space_separated()

        # Calculate metrics for all symbols
        metrics_df = await self._calculate_metrics(symbols, current_date)

        if metrics_df.empty:
            return []

        # Filter out excessively volatile stocks if volatility filter is enabled
        if self.use_volatility_filter and 'atr_ratio' in metrics_df.columns:
            # Keep only stocks with ATR ratio below the maximum threshold
            # or stocks where ATR ratio couldn't be calculated (NaN)
            metrics_df = metrics_df[(metrics_df['atr_ratio'] <= self.max_atr_ratio) | 
                                   (pd.isna(metrics_df['atr_ratio']))]

            if metrics_df.empty:
                print(f"Warning: All stocks filtered out due to excessive volatility.")
                return []

        # Determine ranking column based on criteria
        if self.ranking_criteria == RankingCriteria.PERCENT_ABOVE_AVERAGE:
            ranking_column = 'pct_above_avg'
        elif self.ranking_criteria == RankingCriteria.VOLUME_VS_AVERAGE:
            ranking_column = 'volume_ratio'
        else:  # COMBINED_SCORE
            ranking_column = 'combined_score'

        # Sort by the ranking column in descending order
        sorted_df = metrics_df.sort_values(by=ranking_column, ascending=False)

        # Calculate number of symbols to select (top 10%)
        num_to_select = max(1, int(len(sorted_df) * self.top_percent / 100))

        # Select top symbols
        selected_symbols_df = sorted_df.head(num_to_select)
        selected_symbols = selected_symbols_df['symbol'].tolist()

        # Calculate position sizes based on the selected method
        self._calculate_position_sizes(selected_symbols_df)

        return selected_symbols

    def _calculate_position_sizes(self, selected_symbols_df):
        """
        Calculate position sizes for the selected symbols based on the position sizing method.

        Args:
            selected_symbols_df (pd.DataFrame): DataFrame with selected symbols and their metrics.
        """
        # Reset position sizes dictionary
        self.position_sizes = {}

        if self.position_size_method == PositionSizeMethod.EQUAL_WEIGHT:
            self._calculate_equal_weight_position_sizes(selected_symbols_df)
        elif self.position_size_method == PositionSizeMethod.VOLATILITY_ADJUSTED:
            self._calculate_volatility_adjusted_position_sizes(selected_symbols_df)
        elif self.position_size_method == PositionSizeMethod.PERFORMANCE_BASED:
            self._calculate_performance_based_position_sizes(selected_symbols_df)

    def _calculate_equal_weight_position_sizes(self, selected_symbols_df):
        """
        Calculate equal weight position sizes for the selected symbols.

        Args:
            selected_symbols_df (pd.DataFrame): DataFrame with selected symbols and their metrics.
        """
        num_symbols = len(selected_symbols_df)
        if num_symbols == 0:
            return

        # Equal weight: 1/N for each symbol
        position_size = 1.0 / num_symbols

        for symbol in selected_symbols_df['symbol']:
            self.position_sizes[symbol] = position_size

    def _calculate_volatility_adjusted_position_sizes(self, selected_symbols_df):
        """
        Calculate volatility-adjusted position sizes for the selected symbols.

        Position size is inversely proportional to volatility (higher volatility = smaller position).

        Args:
            selected_symbols_df (pd.DataFrame): DataFrame with selected symbols and their metrics.
        """
        if 'volatility' not in selected_symbols_df.columns:
            # If volatility is not available, fall back to equal weight
            self._calculate_equal_weight_position_sizes(selected_symbols_df)
            return

        # Calculate inverse volatility
        inverse_volatility = 1.0 / selected_symbols_df['volatility']

        # Normalize to sum to 1
        total_inverse_volatility = inverse_volatility.sum()
        if total_inverse_volatility == 0:
            # If total is zero, fall back to equal weight
            self._calculate_equal_weight_position_sizes(selected_symbols_df)
            return

        normalized_inverse_volatility = inverse_volatility / total_inverse_volatility

        # Assign position sizes
        for i, symbol in enumerate(selected_symbols_df['symbol']):
            self.position_sizes[symbol] = normalized_inverse_volatility.iloc[i]

    def _calculate_performance_based_position_sizes(self, selected_symbols_df):
        """
        Calculate performance-based position sizes for the selected symbols.

        Position size is proportional to performance metric (higher performance = larger position).

        Args:
            selected_symbols_df (pd.DataFrame): DataFrame with selected symbols and their metrics.
        """
        # Determine performance metric based on ranking criteria
        if self.ranking_criteria == RankingCriteria.PERCENT_ABOVE_AVERAGE:
            performance_column = 'pct_above_avg'
        elif self.ranking_criteria == RankingCriteria.VOLUME_VS_AVERAGE:
            performance_column = 'volume_ratio'
        else:  # COMBINED_SCORE
            performance_column = 'combined_score'

        # Get performance values
        performance = selected_symbols_df[performance_column]

        # Handle negative values by shifting all values to be positive
        min_performance = performance.min()
        if min_performance < 0:
            performance = performance - min_performance + 0.01  # Add small constant to avoid zeros

        # Normalize to sum to 1
        total_performance = performance.sum()
        if total_performance == 0:
            # If total is zero, fall back to equal weight
            self._calculate_equal_weight_position_sizes(selected_symbols_df)
            return

        normalized_performance = performance / total_performance

        # Assign position sizes
        for i, symbol in enumerate(selected_symbols_df['symbol']):
            self.position_sizes[symbol] = normalized_performance.iloc[i]

    async def generate_signals(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        """
        Generate buy/sell signals for the given symbol and date range.

        For this strategy, we only generate signals for symbols that are in the
        top 10% based on our ranking criteria. We rebalance the selection weekly.

        Args:
            symbol: The stock symbol (e.g., 'MSFT', 'AAPL')
            start_date: The start date for the analysis
            end_date: The end date for the analysis

        Returns:
            pd.DataFrame: DataFrame with dates as index and signals as values

        Raises:
            DataNotFoundError: If data cannot be found or downloaded
            DataProcessingError: If there's an error processing the data
        """
        # Create a date range for the analysis period
        date_range = pd.date_range(start=start_date, end=end_date)

        # Initialize DataFrame with HOLD signals
        signals = self._initialize_signals_dataframe(date_range)

        # Process each date in the range
        for current_date in date_range:
            current_date = current_date.date()

            # Check if we need to rebalance and do so if necessary
            signals = await self._handle_rebalancing(signals, symbol, current_date, start_date)

        return signals

    def _initialize_signals_dataframe(self, date_range):
        """
        Initialize a DataFrame with HOLD signals for the given date range.

        Args:
            date_range (pd.DatetimeIndex): Range of dates for the analysis.

        Returns:
            pd.DataFrame: DataFrame with dates as index, HOLD signals, and position sizes.
        """
        signals = pd.DataFrame(index=date_range, columns=['signal', 'position_size'])
        signals['signal'] = Signal.HOLD.value
        signals['position_size'] = 0.0  # Default position size is 0
        return signals

    async def _handle_rebalancing(self, signals, symbol, current_date, start_date):
        """
        Handle rebalancing of selected symbols and generate signals accordingly.

        Args:
            signals (pd.DataFrame): DataFrame with signals.
            symbol (str): The stock symbol.
            current_date (date): Current date being processed.
            start_date (date): Start date of the analysis.

        Returns:
            pd.DataFrame: Updated signals DataFrame.
        """
        # Check if we need to rebalance
        if self._should_rebalance(current_date):
            # Select top symbols
            self.selected_symbols = await self._select_top_symbols(current_date)
            self.last_rebalance_date = current_date

        # Generate signals based on whether the symbol is in the selected list
        signals = self._generate_signals_for_date(signals, symbol, current_date, start_date)

        return signals

    def _should_rebalance(self, current_date):
        """
        Determine if rebalancing is needed based on the last rebalance date.

        Args:
            current_date (date): Current date being processed.

        Returns:
            bool: True if rebalancing is needed, False otherwise.
        """
        return (self.last_rebalance_date is None or 
                (current_date - self.last_rebalance_date).days >= self.rebalance_days)

    def _generate_signals_for_date(self, signals, symbol, current_date, start_date):
        """
        Generate signals for a specific date based on selected symbols.

        Args:
            signals (pd.DataFrame): DataFrame with signals.
            symbol (str): The stock symbol.
            current_date (date): Current date being processed.
            start_date (date): Start date of the analysis.

        Returns:
            pd.DataFrame: Updated signals DataFrame.
        """
        # Check if we need to apply trailing stop logic
        if self.use_trailing_stop:
            # Apply trailing stop logic if we're in a position
            if symbol in self.position_states and self.position_states[symbol] == 1:
                # Get current price data for the symbol
                try:
                    # Get data for the current date
                    df = self.data_reader.get_data_sync(symbol, current_date, current_date)
                    if not df.empty:
                        current_price = df.iloc[0]['close']

                        # Check if price has fallen below trailing stop
                        if current_price < self.trailing_stops[symbol]:
                            signals.loc[current_date, 'signal'] = Signal.SELL.value
                            # Reset position tracking for this symbol
                            self.position_states[symbol] = 0
                            self.highest_since_buy[symbol] = None
                            self.trailing_stops[symbol] = None
                            return signals

                        # Update highest price and trailing stop
                        self._update_trailing_stop(symbol, current_price)
                except Exception as e:
                    print(f"Error applying trailing stop for {symbol} on {current_date}: {e}")

        # Regular signal generation logic
        if symbol in self.selected_symbols:
            # If the symbol is in our selected list, set a BUY signal
            signals.loc[current_date, 'signal'] = Signal.BUY.value

            # Set position size based on the calculated position sizes
            if symbol in self.position_sizes:
                signals.loc[current_date, 'position_size'] = self.position_sizes[symbol]
            else:
                # If position size is not available, use equal weight as fallback
                num_selected = len(self.selected_symbols)
                signals.loc[current_date, 'position_size'] = 1.0 / max(1, num_selected)

            # Initialize or update position tracking for trailing stop
            if self.use_trailing_stop:
                try:
                    # Get data for the current date
                    df = self.data_reader.get_data_sync(symbol, current_date, current_date)
                    if not df.empty:
                        current_price = df.iloc[0]['close']

                        # Initialize position tracking if not already in position
                        if symbol not in self.position_states or self.position_states[symbol] == 0:
                            self.position_states[symbol] = 1
                            self.highest_since_buy[symbol] = current_price
                            self.trailing_stops[symbol] = current_price * (1 - self.trailing_stop_pct/100)
                except Exception as e:
                    print(f"Error initializing trailing stop for {symbol} on {current_date}: {e}")
        else:
            # If the symbol was previously in our list but no longer is, set a SELL signal
            if current_date > start_date:
                prev_date = (pd.Timestamp(current_date) - pd.Timedelta(days=1)).date()
                if prev_date in signals.index and signals.loc[prev_date, 'signal'] == Signal.BUY.value:
                    signals.loc[current_date, 'signal'] = Signal.SELL.value
                    signals.loc[current_date, 'position_size'] = 0.0  # Reset position size

                    # Reset position tracking for this symbol
                    if self.use_trailing_stop and symbol in self.position_states:
                        self.position_states[symbol] = 0
                        self.highest_since_buy[symbol] = None
                        self.trailing_stops[symbol] = None

        return signals

    def _update_trailing_stop(self, symbol, current_price):
        """
        Update trailing stop values based on current price.

        Args:
            symbol (str): The stock symbol.
            current_price (float): Current price of the symbol.
        """
        # Update highest price since buy if current price is higher
        if self.highest_since_buy[symbol] is None or current_price > self.highest_since_buy[symbol]:
            self.highest_since_buy[symbol] = current_price

        # Update trailing stop based on highest price
        self.trailing_stops[symbol] = self.highest_since_buy[symbol] * (1 - self.trailing_stop_pct/100)
