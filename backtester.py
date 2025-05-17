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
import matplotlib.pyplot as plt
import asyncio
import dask.dataframe as dd
from dask.distributed import Client, LocalCluster
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from functools import partial

from strategies.momentum import Signal
from interfaces.business_logic.backtester_interface import BackTesterInterface, BacktestReportInterface
from interfaces.business_logic.strategy_interface import StrategyInterface
from interfaces.data_access.data_reader_interface import DataReaderInterface


@dataclass
class Trade:
    """Represents a single trade."""
    symbol: str
    entry_date: datetime
    entry_price: float
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None

    @property
    def is_open(self) -> bool:
        """Check if the trade is still open."""
        return self.exit_date is None

    @property
    def duration(self) -> Optional[int]:
        """Get the duration of the trade in days."""
        if not self.exit_date:
            return None
        return (self.exit_date - self.entry_date).days

    @property
    def profit_pct(self) -> Optional[float]:
        """Calculate the profit percentage."""
        if not self.exit_price:
            return None
        return ((self.exit_price - self.entry_price) / self.entry_price) * 100


@dataclass
class BacktestReport(BacktestReportInterface):
    """Contains the results of a backtest."""
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    trades: List[Trade]
    equity_curve: pd.Series

    @property
    def total_return(self) -> float:
        """Calculate the total return percentage."""
        return ((self.final_capital - self.initial_capital) / self.initial_capital) * 100

    @property
    def annualized_return(self) -> float:
        """Calculate the annualized return percentage."""
        days = (self.end_date - self.start_date).days
        years = days / 365
        return ((1 + self.total_return / 100) ** (1 / years) - 1) * 100 if years > 0 else 0

    @property
    def wins(self) -> List[Trade]:
        """Get the winning trades."""
        return [trade for trade in self.trades if trade.profit_pct and trade.profit_pct > 0]

    @property
    def losses(self) -> List[Trade]:
        """Get the losing trades."""
        return [trade for trade in self.trades if trade.profit_pct and trade.profit_pct <= 0]

    @property
    def win_rate(self) -> float:
        """Calculate the win rate."""
        if not self.trades:
            return 0
        return len(self.wins) / len(self.trades) * 100

    @property
    def average_win(self) -> float:
        """Calculate the average winning trade percentage."""
        if not self.wins:
            return 0
        return sum(trade.profit_pct for trade in self.wins) / len(self.wins)

    @property
    def average_loss(self) -> float:
        """Calculate the average losing trade percentage."""
        if not self.losses:
            return 0
        return sum(trade.profit_pct for trade in self.losses) / len(self.losses)

    @property
    def profit_factor(self) -> float:
        """Calculate the profit factor (gross profit / gross loss)."""
        gross_profit = sum(trade.profit_pct for trade in self.wins) if self.wins else 0
        gross_loss = abs(sum(trade.profit_pct for trade in self.losses)) if self.losses else 0
        return gross_profit / gross_loss if gross_loss else float('inf')

    @property
    def max_drawdown(self) -> float:
        """Calculate the maximum drawdown percentage."""
        if self.equity_curve.empty:
            return 0

        # Calculate the running maximum
        running_max = self.equity_curve.cummax()

        # Calculate the drawdown
        drawdown = (self.equity_curve - running_max) / running_max * 100

        # Return the maximum drawdown
        return abs(drawdown.min())

    @property
    def sharpe_ratio(self) -> float:
        """Calculate the Sharpe ratio (assuming risk-free rate of 0)."""
        if self.equity_curve.empty:
            return 0

        # Calculate daily returns
        daily_returns = self.equity_curve.pct_change().dropna()

        # Calculate annualized Sharpe ratio
        if daily_returns.std() == 0:
            return 0

        return (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)

    def plot_equity_curve(self, benchmark_data=None):
        """
        Plot the equity curve.

        Args:
            benchmark_data (pd.Series, optional): Benchmark data to compare against.
        """
        plt.figure(figsize=(12, 6))

        # Plot equity curve
        plt.plot(self.equity_curve.index, self.equity_curve, label=f'{self.symbol} Strategy')

        # Plot benchmark if provided
        if benchmark_data is not None:
            # Normalize benchmark to start at the same value as the strategy
            benchmark_normalized = benchmark_data / benchmark_data.iloc[0] * self.initial_capital
            plt.plot(benchmark_data.index, benchmark_normalized, label='Benchmark', alpha=0.7)

        plt.title(f'Equity Curve for {self.symbol}')
        plt.xlabel('Date')
        plt.ylabel('Capital ($)')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()

        return plt

    def summary(self) -> Dict[str, Any]:
        """Generate a summary of the backtest results."""
        return {
            'Symbol': self.symbol,
            'Period': f"{self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}",
            'Initial Capital': f"${self.initial_capital:.2f}",
            'Final Capital': f"${self.final_capital:.2f}",
            'Total Return': f"{self.total_return:.2f}%",
            'Annualized Return': f"{self.annualized_return:.2f}%",
            'Number of Trades': len(self.trades),
            'Win Rate': f"{self.win_rate:.2f}%",
            'Average Win': f"{self.average_win:.2f}%",
            'Average Loss': f"{self.average_loss:.2f}%",
            'Profit Factor': f"{self.profit_factor:.2f}",
            'Max Drawdown': f"{self.max_drawdown:.2f}%",
            'Sharpe Ratio': f"{self.sharpe_ratio:.2f}"
        }


class BackTester(BackTesterInterface):
    """Backtesting framework for trading strategies."""

    def __init__(self, data_reader: DataReaderInterface, initial_capital: float = 10000, transaction_cost_pct: float = 0.1, 
                 use_dask: bool = True, n_workers: int = None):
        """
        Initialize the backtester.

        Args:
            data_reader: An instance of a class implementing DataReaderInterface to access financial data.
            initial_capital (float): Initial capital for the backtest.
            transaction_cost_pct (float): Transaction cost as a percentage of trade value.
            use_dask (bool): Whether to use dask for parallel processing.
            n_workers (int): Number of workers for dask. If None, uses number of CPU cores.
        """
        self.data_reader = data_reader
        self.initial_capital = initial_capital
        self.transaction_cost_pct = transaction_cost_pct
        self.use_dask = use_dask
        self.n_workers = n_workers

        # Initialize dask client if enabled
        self.dask_client = None
        if self.use_dask:
            try:
                # Create a local cluster with specified number of workers
                cluster = LocalCluster(n_workers=self.n_workers, threads_per_worker=1)
                self.dask_client = Client(cluster)
            except Exception as e:
                print(f"Warning: Failed to initialize dask client: {e}")
                self.use_dask = False

    async def backtest(self, strategy, symbol, start_date, end_date):
        """
        Run a backtest for a given strategy, symbol, and date range.
        Uses dask for parallel processing if enabled.

        Args:
            strategy: A strategy instance that implements generate_signals.
            symbol (str): The stock symbol to backtest.
            start_date: The start date for the backtest.
            end_date: The end date for the backtest.

        Returns:
            BacktestReport: A report containing the backtest results.
        """
        # Get price data
        price_data = await self.data_reader.get_data(symbol, start_date, end_date)

        # Generate signals
        signals = await strategy.generate_signals(symbol, start_date, end_date)

        # Merge price data with signals
        data = pd.merge(price_data, signals, left_index=True, right_index=True, how='left')

        if self.use_dask and len(data) > 1000:  # Only use dask for larger datasets
            try:
                # Define a function to process a chunk of data
                def process_chunk(df, initial_state=None):
                    # Unpack initial state or use defaults
                    if initial_state:
                        chunk_capital, chunk_position, chunk_trades, chunk_current_trade = initial_state
                    else:
                        chunk_capital = self.initial_capital
                        chunk_position = 0
                        chunk_trades = []
                        chunk_current_trade = None

                    # Create equity curve for this chunk
                    chunk_equity = pd.Series(index=df.index, dtype=float)

                    # Process each row in the chunk
                    for date, row in df.iterrows():
                        # Record equity at this point
                        chunk_equity[date] = chunk_capital if chunk_position == 0 else chunk_capital + chunk_position * row['close']

                        # Process signals
                        if row['signal'] == Signal.BUY.value and chunk_position == 0:
                            # Buy signal and no position - enter a new trade
                            chunk_position = chunk_capital / row['close']  # Number of shares
                            chunk_capital -= chunk_position * row['close'] * (1 + self.transaction_cost_pct / 100)
                            chunk_current_trade = Trade(
                                symbol=symbol,
                                entry_date=date,
                                entry_price=row['close']
                            )

                        elif row['signal'] == Signal.SELL.value and chunk_position > 0:
                            # Sell signal and have a position - exit the trade
                            chunk_capital += chunk_position * row['close'] * (1 - self.transaction_cost_pct / 100)

                            # Complete the current trade
                            chunk_current_trade.exit_date = date
                            chunk_current_trade.exit_price = row['close']
                            chunk_trades.append(chunk_current_trade)

                            # Reset position
                            chunk_position = 0
                            chunk_current_trade = None

                    # Return the state and equity curve for this chunk
                    return chunk_capital, chunk_position, chunk_trades, chunk_current_trade, chunk_equity

                # Convert to dask DataFrame
                dask_df = dd.from_pandas(data, npartitions=self.n_workers or 4)

                # Process in parallel using dask
                results = []
                current_state = None

                # Process each partition sequentially, passing state between them
                for i in range(dask_df.npartitions):
                    partition = dask_df.get_partition(i).compute()
                    current_state = process_chunk(partition, current_state)
                    results.append(current_state)

                # Extract final state
                capital, position, trades, current_trade, equity_parts = results[-1]

                # Combine equity curves from all partitions
                equity_curve = pd.concat([result[4] for result in results])

                # Close any open position at the end of the backtest
                if position > 0 and current_trade:
                    last_price = data['close'].iloc[-1]
                    capital += position * last_price * (1 - self.transaction_cost_pct / 100)

                    current_trade.exit_date = data.index[-1]
                    current_trade.exit_price = last_price
                    trades.append(current_trade)

            except Exception as e:
                print(f"Warning: Dask processing failed, falling back to sequential processing: {e}")
                # Fall back to sequential processing
                return await self._backtest_sequential(strategy, symbol, start_date, end_date, data)
        else:
            # Use sequential processing for smaller datasets or if dask is disabled
            return await self._backtest_sequential(strategy, symbol, start_date, end_date, data)

        # Create and return the backtest report
        return BacktestReport(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=capital,
            trades=trades,
            equity_curve=equity_curve
        )

    async def _backtest_sequential(self, strategy, symbol, start_date, end_date, data=None, chunk_size=None):
        """
        Run a backtest sequentially (without dask).

        Args:
            strategy: A strategy instance that implements generate_signals.
            symbol (str): The stock symbol to backtest.
            start_date: The start date for the backtest.
            end_date: The end date for the backtest.
            data: Pre-processed data (optional). If None, data will be fetched and processed.
            chunk_size: If provided, process data in chunks of this size to reduce memory usage.

        Returns:
            BacktestReport: A report containing the backtest results.
        """
        # Initialize variables
        capital = self.initial_capital
        position = 0  # 0 = no position, 1 = long position
        trades = []
        current_trade = None
        equity_curve_data = []

        # Process data in chunks if requested
        if chunk_size is not None and data is None:
            # Get price data in chunks
            price_data_chunks = self.data_reader.get_data(symbol, start_date, end_date, chunk_size=chunk_size)

            # Generate signals in chunks
            signals_chunks = await strategy.generate_signals(symbol, start_date, end_date, chunk_size=chunk_size)

            # Process each chunk
            for price_chunk, signals_chunk in zip(price_data_chunks, signals_chunks):
                if price_chunk.empty or signals_chunk.empty:
                    continue

                # Merge price data with signals for this chunk
                chunk_data = pd.merge(price_chunk, signals_chunk, left_index=True, right_index=True, how='left')

                # Process this chunk
                capital, position, trades, current_trade, chunk_equity = self._process_data_chunk(
                    chunk_data, capital, position, trades, current_trade, symbol
                )

                # Append to equity curve
                equity_curve_data.append(chunk_equity)

            # Combine equity curve data
            if equity_curve_data:
                equity_curve = pd.concat(equity_curve_data)
            else:
                equity_curve = pd.Series(index=pd.date_range(start_date, end_date), dtype=float)
        else:
            # Get and process data if not provided (all at once)
            if data is None:
                # Get price data
                price_data = await self.data_reader.get_data(symbol, start_date, end_date)

                # Generate signals
                signals = await strategy.generate_signals(symbol, start_date, end_date)

                # Merge price data with signals
                data = pd.merge(price_data, signals, left_index=True, right_index=True, how='left')

            # Initialize equity curve
            equity_curve = pd.Series(index=data.index, dtype=float)

            # Process all data at once
            capital, position, trades, current_trade, equity_curve = self._process_data_chunk(
                data, capital, position, trades, current_trade, symbol, equity_curve
            )

        # Create and return the backtest report
        return BacktestReport(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=capital,
            trades=trades,
            equity_curve=equity_curve
        )

    def _process_data_chunk(self, data, capital, position, trades, current_trade, symbol, equity_curve=None):
        """
        Process a chunk of data for backtesting.

        Args:
            data: DataFrame containing price data and signals for this chunk
            capital: Current capital
            position: Current position (0 = no position, shares = long position)
            trades: List of completed trades
            current_trade: Current open trade (if any)
            symbol: Stock symbol
            equity_curve: Existing equity curve Series (optional)

        Returns:
            tuple: (capital, position, trades, current_trade, equity_curve)
        """
        # Initialize equity curve if not provided
        if equity_curve is None:
            equity_curve = pd.Series(index=data.index, dtype=float)

        # Simulate trading for this chunk
        for date, row in data.iterrows():
            # Record equity at this point
            equity_curve[date] = capital if position == 0 else capital + position * row['close']

            # Process signals
            if row['signal'] == Signal.BUY.value and position == 0:
                # Buy signal and no position - enter a new trade
                position = capital / row['close']  # Number of shares
                capital -= position * row['close'] * (1 + self.transaction_cost_pct / 100)  # Deduct transaction costs
                current_trade = Trade(
                    symbol=symbol,
                    entry_date=date,
                    entry_price=row['close']
                )

            elif row['signal'] == Signal.SELL.value and position > 0:
                # Sell signal and have a position - exit the trade
                capital += position * row['close'] * (1 - self.transaction_cost_pct / 100)  # Deduct transaction costs

                # Complete the current trade
                current_trade.exit_date = date
                current_trade.exit_price = row['close']
                trades.append(current_trade)

                # Reset position
                position = 0
                current_trade = None

        # If this is the last chunk, close any open position
        if current_trade and position > 0 and data.index[-1] == data.index.max():
            last_price = data['close'].iloc[-1]
            capital += position * last_price * (1 - self.transaction_cost_pct / 100)

            current_trade.exit_date = data.index[-1]
            current_trade.exit_price = last_price
            trades.append(current_trade)

            # Reset position
            position = 0
            current_trade = None

        return capital, position, trades, current_trade, equity_curve

    async def compare_strategies(self, strategies, symbol, start_date, end_date):
        """
        Compare multiple strategies on the same symbol and date range.
        Runs backtests for all strategies in parallel.

        Args:
            strategies (list): List of strategy instances.
            symbol (str): The stock symbol to backtest.
            start_date: The start date for the backtest.
            end_date: The end date for the backtest.

        Returns:
            dict: A dictionary mapping strategy names to BacktestReport objects.
        """
        # Create a list of tasks for each strategy
        tasks = []
        strategy_names = []

        for strategy in strategies:
            strategy_name = strategy.__class__.__name__
            strategy_names.append(strategy_name)
            tasks.append(self.backtest(strategy, symbol, start_date, end_date))

        # Run all backtests concurrently
        reports = await asyncio.gather(*tasks)

        # Map strategy names to their reports
        results = {name: report for name, report in zip(strategy_names, reports)}

        return results

    async def compare_to_benchmark(self, strategy, symbol, benchmark_symbol, start_date, end_date):
        """
        Compare a strategy to a benchmark.
        Runs the strategy backtest and gets benchmark data concurrently.

        Args:
            strategy: A strategy instance.
            symbol (str): The stock symbol to backtest.
            benchmark_symbol (str): The benchmark symbol (e.g., 'SPY').
            start_date: The start date for the backtest.
            end_date: The end date for the backtest.

        Returns:
            tuple: A tuple containing (strategy_report, benchmark_data).
        """
        # Run the strategy backtest and get benchmark data concurrently
        strategy_backtest_task = self.backtest(strategy, symbol, start_date, end_date)
        benchmark_data_task = self.data_reader.get_data(benchmark_symbol, start_date, end_date)

        strategy_report, benchmark_data = await asyncio.gather(
            strategy_backtest_task, 
            benchmark_data_task
        )

        return strategy_report, benchmark_data['close']
