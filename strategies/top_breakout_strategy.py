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
from datetime import datetime, timedelta
from enum import Enum

from strategies.momentum import MomentumStrategy, Signal
from data_manager.symbol_manager import SymbolManager

class RankingCriteria(Enum):
    """Enum for different ranking criteria."""
    PERCENT_ABOVE_AVERAGE = 1
    VOLUME_VS_AVERAGE = 2
    COMBINED_SCORE = 3

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
                 rebalance_days=7):
        """
        Initialize the Top Breakout strategy.

        Args:
            data_reader: An instance of DataReader.
            symbols_file (str): Path to the CSV file containing symbols.
            avg_period (int): Period for calculating the average price (default: 20 days).
            top_percent (int): Percentage of top stocks to select (default: 10%).
            ranking_criteria (RankingCriteria): Criteria for ranking stocks.
            rebalance_days (int): Number of days between rebalancing (default: 7 days).
        """
        super().__init__(data_reader)
        self.symbols_file = symbols_file
        self.avg_period = avg_period
        self.top_percent = top_percent
        self.ranking_criteria = ranking_criteria
        self.rebalance_days = rebalance_days

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
                # Get data for the symbol
                df = await self.data_reader.get_data(symbol, start_date, current_date)

                if df.empty:
                    continue

                # Calculate 20-day average price and volume
                # Create a copy of the DataFrame to avoid SettingWithCopyWarning
                df = df.copy()

                # Use .loc to set values to avoid SettingWithCopyWarning
                df.loc[:, 'avg_price'] = df['close'].rolling(window=self.avg_period).mean()
                df.loc[:, 'avg_volume'] = df['volume'].rolling(window=self.avg_period).mean()

                # Get the latest data point
                latest = df.iloc[-1]

                # Calculate metrics
                pct_above_avg = (latest['close'] / latest['avg_price'] - 1) * 100
                volume_ratio = latest['volume'] / latest['avg_volume']

                # Calculate combined score (equal weighting)
                combined_score = (pct_above_avg + volume_ratio) / 2

                # Add to metrics list
                metrics.append({
                    'symbol': symbol,
                    'pct_above_avg': pct_above_avg,
                    'volume_ratio': volume_ratio,
                    'combined_score': combined_score,
                    'close': latest['close'],
                    'volume': latest['volume']
                })

            except Exception as e:
                print(f"Error processing {symbol}: {e}")
                continue

        # Convert to DataFrame
        metrics_df = pd.DataFrame(metrics)

        return metrics_df

    async def _select_top_symbols(self, current_date):
        """
        Select the top symbols based on the ranking criteria.

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
        selected_symbols = sorted_df.head(num_to_select)['symbol'].tolist()

        return selected_symbols

    async def generate_signals(self, symbol, start_date, end_date):
        """
        Generate buy/sell signals for the given symbol and date range.

        For this strategy, we only generate signals for symbols that are in the
        top 10% based on our ranking criteria. We rebalance the selection weekly.

        Args:
            symbol (str): The stock symbol.
            start_date: The start date for the analysis.
            end_date: The end date for the analysis.

        Returns:
            pd.DataFrame: DataFrame with dates as index and signals as values.
        """
        # Create a date range for the analysis period
        date_range = pd.date_range(start=start_date, end=end_date)

        # Initialize DataFrame with HOLD signals
        signals = pd.DataFrame(index=date_range, columns=['signal'])
        signals['signal'] = Signal.HOLD.value

        # Process each date in the range
        for current_date in date_range:
            current_date = current_date.date()

            # Check if we need to rebalance
            if (self.last_rebalance_date is None or 
                (current_date - self.last_rebalance_date).days >= self.rebalance_days):

                # Select top symbols
                self.selected_symbols = await self._select_top_symbols(current_date)
                self.last_rebalance_date = current_date

            # Generate signals only for selected symbols
            if symbol in self.selected_symbols:
                # If the symbol is in our selected list, set a BUY signal
                signals.loc[current_date, 'signal'] = Signal.BUY.value
            else:
                # If the symbol was previously in our list but no longer is, set a SELL signal
                if current_date > start_date:
                    prev_date = (pd.Timestamp(current_date) - pd.Timedelta(days=1)).date()
                    if prev_date in signals.index and signals.loc[prev_date, 'signal'] == Signal.BUY.value:
                        signals.loc[current_date, 'signal'] = Signal.SELL.value

        return signals
