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


class TestBacktesterChunks(unittest.TestCase):
    """Test cases for chunk processing in the BackTester class."""

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

        # Initialize the backtester
        self.backtester = BackTester(
            data_reader=self.data_reader,
            initial_capital=10000,
            transaction_cost_pct=0.1
        )

    async def test_backtest_sequential_with_chunks(self):
        """Test backtesting with data chunks."""
        # Create chunks of data
        chunk_size = 10
        chunks = []
        for i in range(0, len(self.sample_data), chunk_size):
            chunks.append(self.sample_data.iloc[i:i+chunk_size].copy())

        # Configure the mock data_reader to return chunks
        self.data_reader.get_data = mock.AsyncMock()
        self.data_reader.get_data.return_value = chunks

        # Create signals with a buy at the beginning and sell at the end
        signals_chunks = []
        for i, chunk in enumerate(chunks):
            if i == 0:  # First chunk has a buy signal
                signals = pd.DataFrame({
                    'signal': [Signal.BUY.value] + [Signal.HOLD.value] * (len(chunk) - 1)
                }, index=chunk.index)
            elif i == len(chunks) - 1:  # Last chunk has a sell signal
                signals = pd.DataFrame({
                    'signal': [Signal.HOLD.value] * (len(chunk) - 1) + [Signal.SELL.value]
                }, index=chunk.index)
            else:  # Middle chunks have hold signals
                signals = pd.DataFrame({
                    'signal': [Signal.HOLD.value] * len(chunk)
                }, index=chunk.index)
            signals_chunks.append(signals)

        # Create a mock strategy that returns our signal chunks
        mock_strategy = mock.MagicMock()
        mock_strategy.generate_signals = mock.AsyncMock()
        mock_strategy.generate_signals.return_value = signals_chunks

        # Run the backtest with chunks
        report = await self.backtester._backtest_sequential(
            strategy=mock_strategy,
            symbol='AAPL',
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 31),
            chunk_size=chunk_size
        )

        # Verify the results
        self.assertEqual(report.symbol, 'AAPL')
        self.assertEqual(len(report.trades), 1)  # One complete trade

        # Check the trade details
        trade = report.trades[0]
        self.assertEqual(trade.symbol, 'AAPL')
        self.assertEqual(trade.entry_date, date(2023, 1, 1))  # Buy signal in first chunk
        self.assertEqual(trade.exit_date, date(2023, 1, 31))  # Sell signal in last chunk

        # Verify that profit was made (since prices are increasing)
        self.assertGreater(trade.exit_price, trade.entry_price)
        self.assertGreater(trade.profit_pct, 0)

        # Verify that final capital is greater than initial (profitable trade)
        self.assertGreater(report.final_capital, report.initial_capital)

    async def test_process_data_chunk(self):
        """Test the _process_data_chunk method directly."""
        # Create a small chunk of data
        dates = pd.date_range(start='2023-01-01', end='2023-01-05', freq='D')
        data_chunk = pd.DataFrame({
            'open': [100, 102, 104, 106, 108],
            'high': [105, 107, 109, 111, 113],
            'low': [95, 97, 99, 101, 103],
            'close': [102, 104, 106, 108, 110],
            'signal': [Signal.BUY.value, Signal.HOLD.value, Signal.HOLD.value, Signal.HOLD.value, Signal.SELL.value]
        }, index=dates.date)

        # Initial state
        capital = 10000
        position = 0
        trades = []
        current_trade = None
        symbol = 'AAPL'

        # Process the chunk
        capital, position, trades, current_trade, equity_curve = self.backtester._process_data_chunk(
            data=data_chunk,
            capital=capital,
            position=position,
            trades=trades,
            current_trade=current_trade,
            symbol=symbol
        )

        # Verify the results
        self.assertEqual(len(trades), 1)  # One complete trade
        self.assertEqual(position, 0)  # No position at the end
        self.assertIsNone(current_trade)  # No open trade at the end

        # Check the trade details
        trade = trades[0]
        self.assertEqual(trade.symbol, 'AAPL')
        self.assertEqual(trade.entry_date, date(2023, 1, 1))  # Buy signal on first day
        self.assertEqual(trade.exit_date, date(2023, 1, 5))  # Sell signal on last day
        self.assertEqual(trade.entry_price, 102)
        self.assertEqual(trade.exit_price, 110)

        # Verify that profit was made
        self.assertGreater(trade.profit_pct, 0)
        self.assertGreater(capital, 10000)  # Capital increased

        # Verify equity curve
        self.assertEqual(len(equity_curve), 5)  # One point for each day
        self.assertTrue(all(not pd.isna(value) for value in equity_curve))

    async def test_error_handling_missing_data(self):
        """Test error handling when data is missing."""
        # Configure the mock data_reader to return empty data
        self.data_reader.get_data = mock.AsyncMock()
        self.data_reader.get_data.return_value = pd.DataFrame()

        # Create a mock strategy that returns empty signals
        mock_strategy = mock.MagicMock()
        mock_strategy.generate_signals = mock.AsyncMock()
        mock_strategy.generate_signals.return_value = pd.DataFrame()

        # Run the backtest
        report = await self.backtester.backtest(
            strategy=mock_strategy,
            symbol='AAPL',
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 31)
        )

        # Verify the results
        self.assertEqual(report.symbol, 'AAPL')
        self.assertEqual(len(report.trades), 0)  # No trades
        self.assertEqual(report.final_capital, 10000)  # Capital unchanged
        self.assertTrue(report.equity_curve.empty)  # Empty equity curve

    async def test_short_backtest(self):
        """Test a very short backtest (1-2 days)."""
        # Create a small dataset
        dates = pd.date_range(start='2023-01-01', end='2023-01-02', freq='D')
        short_data = pd.DataFrame({
            'open': [100, 102],
            'high': [105, 107],
            'low': [95, 97],
            'close': [102, 104],
            'adjusted_close': [102, 104],
            'volume': [5000, 6000]
        }, index=dates.date)

        # Configure the mock data_reader to return the short data
        self.data_reader.get_data = mock.AsyncMock()
        self.data_reader.get_data.return_value = short_data

        # Create signals with a buy on day 1 and sell on day 2
        signals = pd.DataFrame({
            'signal': [Signal.BUY.value, Signal.SELL.value]
        }, index=dates.date)

        # Create a mock strategy that returns our signals
        mock_strategy = mock.MagicMock()
        mock_strategy.generate_signals = mock.AsyncMock()
        mock_strategy.generate_signals.return_value = signals

        # Run the backtest
        report = await self.backtester.backtest(
            strategy=mock_strategy,
            symbol='AAPL',
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 2)
        )

        # Verify the results
        self.assertEqual(report.symbol, 'AAPL')
        self.assertEqual(len(report.trades), 1)  # One complete trade

        # Check the trade details
        trade = report.trades[0]
        self.assertEqual(trade.symbol, 'AAPL')
        self.assertEqual(trade.entry_date, date(2023, 1, 1))
        self.assertEqual(trade.exit_date, date(2023, 1, 2))
        self.assertEqual(trade.entry_price, 102)
        self.assertEqual(trade.exit_price, 104)

        # Verify that profit was made
        self.assertGreater(trade.profit_pct, 0)
        self.assertGreater(report.final_capital, 10000)


# Create an AsyncioTestCase class to handle async tests
class AsyncioTestCase(unittest.TestCase):
    """Base class for asyncio test cases."""

    def run_async(self, coro):
        """Run a coroutine in the event loop."""
        return asyncio.run(coro)


# Modify the TestBacktesterChunks class to use AsyncioTestCase
TestBacktesterChunks.__bases__ = (AsyncioTestCase,)


# Wrap async test methods to run them with run_async
for name in dir(TestBacktesterChunks):
    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestBacktesterChunks, name)):
        method = getattr(TestBacktesterChunks, name)

        def wrapper(self, method=method):
            return self.run_async(method(self))

        setattr(TestBacktesterChunks, name, wrapper)


if __name__ == '__main__':
    unittest.main()
