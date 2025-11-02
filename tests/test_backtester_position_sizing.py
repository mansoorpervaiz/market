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


class TestBacktesterPositionSizing(unittest.TestCase):
    """Test cases for position sizing in the BackTester class."""

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

    async def test_position_sizing_in_backtester(self):
        """Test that the BackTester correctly uses position_size values from signals."""
        # Configure the mock data_reader to return the sample data
        async def mock_get_data(*args, **kwargs):
            return self.sample_data.copy()

        self.data_reader.get_data = mock_get_data

        # Create signals with position_size column
        dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
        signals = pd.DataFrame({
            'signal': [Signal.HOLD.value] * 5 + [Signal.BUY.value] + [Signal.HOLD.value] * 20 + [Signal.SELL.value] + [Signal.HOLD.value] * 4,
            'position_size': [0.0] * 5 + [0.5] + [0.0] * 20 + [0.0] + [0.0] * 4  # Allocate 50% of capital
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

        # Verify that the strategy's generate_signals method was called
        mock_strategy.generate_signals.assert_called_once()

        # Verify the backtest results
        self.assertEqual(report.symbol, 'AAPL')
        self.assertEqual(len(report.trades), 1)  # One complete trade

        # Verify that only 50% of capital was allocated to the position
        # The entry price is the close price on the day of the BUY signal (index 5)
        entry_price = self.sample_data.iloc[5]['close']
        # The exit price is the close price on the day of the SELL signal (index 26)
        exit_price = self.sample_data.iloc[26]['close']

        # Calculate expected position size (number of shares)
        expected_position_size = (10000 * 0.5) / entry_price

        # Calculate expected profit
        expected_profit = expected_position_size * (exit_price - entry_price)
        # Subtract transaction costs
        expected_profit -= expected_position_size * entry_price * 0.1 / 100  # Buy transaction cost
        expected_profit -= expected_position_size * exit_price * 0.1 / 100   # Sell transaction cost

        # Calculate expected final capital
        expected_final_capital = 10000 + expected_profit

        # Verify that the final capital is close to the expected value
        self.assertAlmostEqual(report.final_capital, expected_final_capital, delta=0.01)

    async def test_multiple_position_sizes(self):
        """Test that the BackTester correctly handles multiple trades with different position sizes."""
        # Configure the mock data_reader to return the sample data
        async def mock_get_data(*args, **kwargs):
            return self.sample_data.copy()

        self.data_reader.get_data = mock_get_data

        # Create signals with position_size column for multiple trades
        dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
        signals = pd.DataFrame({
            'signal': [Signal.BUY.value] + [Signal.HOLD.value] * 9 + [Signal.SELL.value] + 
                     [Signal.HOLD.value] * 4 + [Signal.BUY.value] + [Signal.HOLD.value] * 9 + [Signal.SELL.value] + [Signal.HOLD.value] * 5,
            'position_size': [0.3] + [0.0] * 9 + [0.0] + 
                            [0.0] * 4 + [0.7] + [0.0] * 9 + [0.0] + [0.0] * 5  # First trade: 30%, Second trade: 70%
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

        # Verify the backtest results
        self.assertEqual(report.symbol, 'AAPL')
        self.assertEqual(len(report.trades), 2)  # Two complete trades

        # Verify that the correct amount of capital was allocated to each position
        # For this test, we'll verify that the final capital is what we expect
        # based on the position sizes and price movements

        # Calculate expected final capital
        # First trade: 30% of initial capital
        first_entry_price = self.sample_data.iloc[0]['close']
        first_exit_price = self.sample_data.iloc[10]['close']
        first_position_size = (10000 * 0.3) / first_entry_price
        first_profit = first_position_size * (first_exit_price - first_entry_price)
        first_profit -= first_position_size * first_entry_price * 0.1 / 100  # Buy transaction cost
        first_profit -= first_position_size * first_exit_price * 0.1 / 100   # Sell transaction cost

        # Capital after first trade
        capital_after_first_trade = 10000 + first_profit

        # Second trade: 70% of remaining capital
        second_entry_price = self.sample_data.iloc[15]['close']
        second_exit_price = self.sample_data.iloc[25]['close']
        second_position_size = (capital_after_first_trade * 0.7) / second_entry_price
        second_profit = second_position_size * (second_exit_price - second_entry_price)
        second_profit -= second_position_size * second_entry_price * 0.1 / 100  # Buy transaction cost
        second_profit -= second_position_size * second_exit_price * 0.1 / 100   # Sell transaction cost

        # Final capital
        expected_final_capital = capital_after_first_trade + second_profit

        # Verify that the final capital is close to the expected value
        self.assertAlmostEqual(report.final_capital, expected_final_capital, delta=1.0)


class AsyncioTestCase(unittest.TestCase):
    """Base class for asyncio test cases."""

    def run_async(self, coro):
        """Run a coroutine in the event loop."""
        return asyncio.run(coro)


# Modify the TestBacktesterPositionSizing class to use AsyncioTestCase
TestBacktesterPositionSizing.__bases__ = (AsyncioTestCase,)


# Wrap async test methods to run them with run_async
for name in dir(TestBacktesterPositionSizing):
    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestBacktesterPositionSizing, name)):
        method = getattr(TestBacktesterPositionSizing, name)

        def wrapper(self, method=method):
            return self.run_async(method(self))

        setattr(TestBacktesterPositionSizing, name, wrapper)


if __name__ == '__main__':
    unittest.main()
