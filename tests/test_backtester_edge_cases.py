import unittest
import sys
import os
import asyncio
from datetime import date
from unittest import mock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np

from data_manager.data_reader import DataReader
from strategies.momentum import Signal
from backtester import BackTester, Trade


class TestBacktesterEdgeCases(unittest.TestCase):
    """Test cases for edge cases in the BackTester class."""

    def setUp(self):
        """Set up test fixtures."""
        self.data_reader = mock.MagicMock(spec=DataReader)

        # Create sample data for testing
        dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
        self.sample_data = pd.DataFrame({
            'open': np.linspace(100, 120, len(dates)),
            'high': np.linspace(105, 125, len(dates)),
            'low': np.linspace(95, 115, len(dates)),
            'close': np.linspace(102, 122, len(dates)),
            'adjusted_close': np.linspace(102, 122, len(dates)),
            'volume': np.random.randint(1000, 10000, len(dates))
        }, index=dates.date)

    async def test_invalid_signals(self):
        """Test backtesting with invalid signals."""
        # Configure the mock data_reader to return the sample data
        self.data_reader.get_data = mock.AsyncMock()
        self.data_reader.get_data.return_value = self.sample_data.copy()

        # Create signals with invalid values
        dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
        signals = pd.DataFrame({
            'signal': [Signal.BUY.value] + ['INVALID'] * 5 + [Signal.SELL.value] + [Signal.HOLD.value] * 24
        }, index=dates.date)

        # Create a mock strategy that returns our signals
        mock_strategy = mock.MagicMock()
        mock_strategy.generate_signals = mock.AsyncMock()
        mock_strategy.generate_signals.return_value = signals

        # Create a backtester
        backtester = BackTester(
            data_reader=self.data_reader,
            initial_capital=10000,
            transaction_cost_pct=0.1
        )

        # Run the backtest
        report = await backtester.backtest(
            strategy=mock_strategy,
            symbol='AAPL',
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 31)
        )

        # Verify the results - invalid signals should be ignored
        self.assertEqual(report.symbol, 'AAPL')
        self.assertEqual(len(report.trades), 1)  # One complete trade

        # Check the trade details
        trade = report.trades[0]
        self.assertEqual(trade.symbol, 'AAPL')
        self.assertEqual(trade.entry_date, date(2023, 1, 1))  # Buy signal on first day
        self.assertEqual(trade.exit_date, date(2023, 1, 7))  # Sell signal on day 7

    async def test_different_transaction_costs(self):
        """Test backtesting with different transaction costs."""
        # Configure the mock data_reader to return the sample data
        self.data_reader.get_data = mock.AsyncMock()
        self.data_reader.get_data.return_value = self.sample_data.copy()

        # Create signals with one buy and one sell
        dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
        signals = pd.DataFrame({
            'signal': [Signal.BUY.value] + [Signal.HOLD.value] * 29 + [Signal.SELL.value]
        }, index=dates.date)

        # Create a mock strategy that returns our signals
        mock_strategy = mock.MagicMock()
        mock_strategy.generate_signals = mock.AsyncMock()
        mock_strategy.generate_signals.return_value = signals

        # Test with different transaction costs
        transaction_costs = [0.0, 0.1, 0.5, 1.0, 2.0]
        final_capitals = []

        for cost in transaction_costs:
            # Create a backtester with this transaction cost
            backtester = BackTester(
                data_reader=self.data_reader,
                initial_capital=10000,
                transaction_cost_pct=cost
            )

            # Run the backtest
            report = await backtester.backtest(
                strategy=mock_strategy,
                symbol='AAPL',
                start_date=date(2023, 1, 1),
                end_date=date(2023, 1, 31)
            )

            # Store the final capital
            final_capitals.append(report.final_capital)

        # Verify that higher transaction costs result in lower final capital
        for i in range(1, len(transaction_costs)):
            self.assertLess(final_capitals[i], final_capitals[i-1])

    async def test_multiple_consecutive_signals(self):
        """Test backtesting with multiple consecutive buy/sell signals."""
        # Configure the mock data_reader to return the sample data
        self.data_reader.get_data = mock.AsyncMock()
        self.data_reader.get_data.return_value = self.sample_data.copy()

        # Create signals with multiple consecutive buys and sells
        dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
        signals = pd.DataFrame({
            'signal': [Signal.BUY.value, Signal.BUY.value, Signal.HOLD.value, Signal.HOLD.value, Signal.SELL.value, 
                      Signal.SELL.value, Signal.HOLD.value, Signal.BUY.value, Signal.HOLD.value, Signal.SELL.value] + 
                      [Signal.HOLD.value] * 21
        }, index=dates.date)

        # Create a mock strategy that returns our signals
        mock_strategy = mock.MagicMock()
        mock_strategy.generate_signals = mock.AsyncMock()
        mock_strategy.generate_signals.return_value = signals

        # Create a backtester
        backtester = BackTester(
            data_reader=self.data_reader,
            initial_capital=10000,
            transaction_cost_pct=0.1
        )

        # Run the backtest
        report = await backtester.backtest(
            strategy=mock_strategy,
            symbol='AAPL',
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 31)
        )

        # Verify the results - only the first buy and first sell after that should be processed
        self.assertEqual(report.symbol, 'AAPL')
        self.assertEqual(len(report.trades), 2)  # Two complete trades

        # Check the first trade
        trade1 = report.trades[0]
        self.assertEqual(trade1.symbol, 'AAPL')
        self.assertEqual(trade1.entry_date, date(2023, 1, 1))  # First buy signal
        self.assertEqual(trade1.exit_date, date(2023, 1, 5))  # First sell signal after buy

        # Check the second trade
        trade2 = report.trades[1]
        self.assertEqual(trade2.symbol, 'AAPL')
        self.assertEqual(trade2.entry_date, date(2023, 1, 8))  # Second buy signal
        self.assertEqual(trade2.exit_date, date(2023, 1, 10))  # Second sell signal

    async def test_no_sell_signal(self):
        """Test backtesting with a buy signal but no sell signal."""
        # Configure the mock data_reader to return the sample data
        self.data_reader.get_data = mock.AsyncMock()
        self.data_reader.get_data.return_value = self.sample_data.copy()

        # Create signals with only a buy signal
        dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
        signals = pd.DataFrame({
            'signal': [Signal.BUY.value] + [Signal.HOLD.value] * 30
        }, index=dates.date)

        # Create a mock strategy that returns our signals
        mock_strategy = mock.MagicMock()
        mock_strategy.generate_signals = mock.AsyncMock()
        mock_strategy.generate_signals.return_value = signals

        # Create a backtester
        backtester = BackTester(
            data_reader=self.data_reader,
            initial_capital=10000,
            transaction_cost_pct=0.1
        )

        # Run the backtest
        report = await backtester.backtest(
            strategy=mock_strategy,
            symbol='AAPL',
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 31)
        )

        # Verify the results - position should be closed at the end of the backtest
        self.assertEqual(report.symbol, 'AAPL')
        self.assertEqual(len(report.trades), 1)  # One trade

        # Check the trade details
        trade = report.trades[0]
        self.assertEqual(trade.symbol, 'AAPL')
        self.assertEqual(trade.entry_date, date(2023, 1, 1))  # Buy signal on first day
        self.assertEqual(trade.exit_date, date(2023, 1, 31))  # Exit at the end of the backtest


# Create an AsyncioTestCase class to handle async tests
class AsyncioTestCase(unittest.TestCase):
    """Base class for asyncio test cases."""

    def run_async(self, coro):
        """Run a coroutine in the event loop."""
        return asyncio.run(coro)


# Modify the TestBacktesterEdgeCases class to use AsyncioTestCase
TestBacktesterEdgeCases.__bases__ = (AsyncioTestCase,)


# Wrap async test methods to run them with run_async
for name in dir(TestBacktesterEdgeCases):
    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestBacktesterEdgeCases, name)):
        method = getattr(TestBacktesterEdgeCases, name)

        def wrapper(self, method=method):
            return self.run_async(method(self))

        setattr(TestBacktesterEdgeCases, name, wrapper)


if __name__ == '__main__':
    unittest.main()
