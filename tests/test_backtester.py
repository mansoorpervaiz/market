# Copyright (c) 2025 Mansoor Pervaiz
# All rights reserved.
#
# This file is part of a proprietary software project.
# Unauthorized copying, distribution, modification, or use of this file,
# via any medium, is strictly prohibited unless explicit permission is granted
# by the author.
#
# For licensing inquiries, contact: mansoorpervaizdev@gmail.com

import unittest
import sys
import os
import asyncio
from datetime import date, timedelta
from unittest import mock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np

from data_manager.data_reader import DataReader, FieldName
from strategies.momentum import Signal, MomentumStrategy
from backtester import BackTester, BacktestReport, Trade


class MockStrategy(MomentumStrategy):
    """A mock strategy for testing the backtester."""

    def __init__(self, data_reader, signals, name=None):
        """
        Initialize with predetermined signals.

        Args:
            data_reader: DataReader instance
            signals: List of signal values to return
            name: Optional custom name for the strategy
        """
        super().__init__(data_reader)
        self.signals = signals
        self._name = name

    @property
    def __class__(self):
        # This allows us to customize the class name for testing
        if self._name:
            return type(self._name, (MomentumStrategy,), {})

    async def generate_signals(self, symbol, start_date, end_date):
        """Return predetermined signals."""
        # Create a DataFrame with the signals
        dates = pd.date_range(start=start_date, end=end_date, freq='D')

        # If we have fewer signals than dates, pad with HOLD signals
        if len(self.signals) < len(dates):
            signals = self.signals + [Signal.HOLD.value] * (len(dates) - len(self.signals))
        else:
            signals = self.signals[:len(dates)]

        return pd.DataFrame({'signal': signals}, index=dates.date)


class TestBackTester(unittest.TestCase):
    """Test cases for the backtesting framework."""

    def setUp(self):
        """Set up test fixtures."""
        self.data_reader = mock.MagicMock(spec=DataReader)

        # Create sample price data
        dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
        self.sample_data = pd.DataFrame({
            'open': np.linspace(100, 120, len(dates)),
            'high': np.linspace(105, 125, len(dates)),
            'low': np.linspace(95, 115, len(dates)),
            'close': np.linspace(102, 122, len(dates)),
            'adjusted_close': np.linspace(102, 122, len(dates)),
            'volume': np.random.randint(1000, 10000, len(dates))
        }, index=dates.date)

        # Initialize the backtester
        self.backtester = BackTester(
            data_reader=self.data_reader,
            initial_capital=10000,
            transaction_cost_pct=0.1
        )

    def test_backtest_no_trades(self):
        """Test backtesting with no trades."""
        # Configure the mock data_reader to return the sample data directly
        async def mock_get_data(*args, **kwargs):
            return self.sample_data.copy()

        self.data_reader.get_data = mock_get_data

        # Create a strategy that generates no signals
        strategy = MockStrategy(
            data_reader=self.data_reader,
            signals=[Signal.HOLD.value] * 31
        )

        # Run the backtest
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 31)
        report = asyncio.run(self.backtester.backtest(
            strategy=strategy,
            symbol='AAPL',
            start_date=start_date,
            end_date=end_date
        ))

        # Verify the results
        self.assertEqual(report.symbol, 'AAPL')
        self.assertEqual(report.initial_capital, 10000)
        self.assertEqual(report.final_capital, 10000)  # No change in capital
        self.assertEqual(len(report.trades), 0)  # No trades

    def test_backtest_one_complete_trade(self):
        """Test backtesting with one complete trade (buy and sell)."""
        # Configure the mock data_reader to return the sample data directly
        async def mock_get_data(*args, **kwargs):
            return self.sample_data.copy()

        self.data_reader.get_data = mock_get_data

        # Create a strategy that generates one buy and one sell signal
        signals = [Signal.HOLD.value] * 5 + [Signal.BUY.value] + [Signal.HOLD.value] * 15 + [Signal.SELL.value] + [Signal.HOLD.value] * 9
        strategy = MockStrategy(
            data_reader=self.data_reader,
            signals=signals
        )

        # Run the backtest
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 31)
        report = asyncio.run(self.backtester.backtest(
            strategy=strategy,
            symbol='AAPL',
            start_date=start_date,
            end_date=end_date
        ))

        # Verify the results
        self.assertEqual(report.symbol, 'AAPL')
        self.assertEqual(len(report.trades), 1)  # One complete trade

        # Check the trade details
        trade = report.trades[0]
        self.assertEqual(trade.symbol, 'AAPL')
        self.assertEqual(trade.entry_date, date(2023, 1, 6))  # Buy signal on day 5
        self.assertEqual(trade.exit_date, date(2023, 1, 22))  # Sell signal on day 21

        # Verify that profit was made (since prices are increasing)
        self.assertGreater(trade.exit_price, trade.entry_price)
        self.assertGreater(trade.profit_pct, 0)

        # Verify that final capital is greater than initial (profitable trade)
        self.assertGreater(report.final_capital, report.initial_capital)

    def test_backtest_open_trade_at_end(self):
        """Test backtesting with a trade that is still open at the end."""
        # Configure the mock data_reader to return the sample data directly
        async def mock_get_data(*args, **kwargs):
            return self.sample_data.copy()

        self.data_reader.get_data = mock_get_data

        # Create a strategy that generates one buy signal but no sell
        signals = [Signal.HOLD.value] * 10 + [Signal.BUY.value] + [Signal.HOLD.value] * 20
        strategy = MockStrategy(
            data_reader=self.data_reader,
            signals=signals
        )

        # Run the backtest
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 31)
        report = asyncio.run(self.backtester.backtest(
            strategy=strategy,
            symbol='AAPL',
            start_date=start_date,
            end_date=end_date
        ))

        # Verify the results
        self.assertEqual(report.symbol, 'AAPL')
        self.assertEqual(len(report.trades), 1)  # One trade

        # Check the trade details
        trade = report.trades[0]
        self.assertEqual(trade.symbol, 'AAPL')
        self.assertEqual(trade.entry_date, date(2023, 1, 11))  # Buy signal on day 10
        self.assertEqual(trade.exit_date, date(2023, 1, 31))  # Exit at the end of the backtest

        # Verify that profit was made (since prices are increasing)
        self.assertGreater(trade.exit_price, trade.entry_price)
        self.assertGreater(trade.profit_pct, 0)

        # Verify that final capital is greater than initial (profitable trade)
        self.assertGreater(report.final_capital, report.initial_capital)

    def test_compare_strategies(self):
        """Test comparing multiple strategies."""
        # Configure the mock data_reader to return the sample data directly
        async def mock_get_data(*args, **kwargs):
            return self.sample_data.copy()

        self.data_reader.get_data = mock_get_data

        # Create two strategies with different signals and names
        strategy1 = MockStrategy(
            data_reader=self.data_reader,
            signals=[Signal.BUY.value] + [Signal.HOLD.value] * 29 + [Signal.SELL.value],
            name="EarlyBuyStrategy"
        )

        strategy2 = MockStrategy(
            data_reader=self.data_reader,
            signals=[Signal.HOLD.value] * 15 + [Signal.BUY.value] + [Signal.HOLD.value] * 14 + [Signal.SELL.value],
            name="LateBuyStrategy"
        )

        # Run the comparison
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 31)
        results = asyncio.run(self.backtester.compare_strategies(
            strategies=[strategy1, strategy2],
            symbol='AAPL',
            start_date=start_date,
            end_date=end_date
        ))

        # Verify the results
        self.assertEqual(len(results), 2)
        self.assertIn('EarlyBuyStrategy', results)
        self.assertIn('LateBuyStrategy', results)

        # Both strategies should have one trade
        for strategy_name, report in results.items():
            self.assertEqual(len(report.trades), 1)

        # EarlyBuyStrategy should have a higher return (buys earlier)
        self.assertGreater(results['EarlyBuyStrategy'].total_return, 0)

    def test_compare_to_benchmark(self):
        """Test comparing a strategy to a benchmark."""
        # Create benchmark data (SPY)
        dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
        benchmark_data = pd.DataFrame({
            'open': np.linspace(400, 410, len(dates)),
            'high': np.linspace(405, 415, len(dates)),
            'low': np.linspace(395, 405, len(dates)),
            'close': np.linspace(402, 412, len(dates)),
            'adjusted_close': np.linspace(402, 412, len(dates)),
            'volume': np.random.randint(10000, 100000, len(dates))
        }, index=dates.date)

        # Configure the mock data_reader to return different data based on the symbol
        async def mock_get_data(symbol, *args, **kwargs):
            if symbol == 'AAPL':
                return self.sample_data.copy()
            elif symbol == 'SPY':
                return benchmark_data
            else:
                return None

        self.data_reader.get_data = mock_get_data

        # Create a strategy
        strategy = MockStrategy(
            data_reader=self.data_reader,
            signals=[Signal.BUY.value] + [Signal.HOLD.value] * 29 + [Signal.SELL.value]
        )

        # Run the comparison
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 31)

        # Create a mock report
        mock_report = BacktestReport(
            symbol='AAPL',
            start_date=start_date,
            end_date=end_date,
            initial_capital=10000,
            final_capital=11000,
            trades=[
                Trade(
                    symbol='AAPL',
                    entry_date=date(2023, 1, 1),
                    entry_price=102,
                    exit_date=date(2023, 1, 31),
                    exit_price=122
                )
            ],
            equity_curve=pd.Series(
                np.linspace(10000, 11000, len(dates)),
                index=dates.date
            )
        )

        # Mock the backtest method to return the predefined report
        async def mock_backtest(*args, **kwargs):
            return mock_report

        # Patch the backtest method
        with mock.patch.object(self.backtester, 'backtest', mock_backtest):
            # Run the comparison
            strategy_report, benchmark_series = asyncio.run(self.backtester.compare_to_benchmark(
                strategy=strategy,
                symbol='AAPL',
                benchmark_symbol='SPY',
                start_date=start_date,
                end_date=end_date
            ))

        # Verify the results
        self.assertEqual(strategy_report.symbol, 'AAPL')
        self.assertEqual(len(strategy_report.trades), 1)
        self.assertEqual(len(benchmark_series), len(dates))


if __name__ == '__main__':
    unittest.main()
