import unittest
import sys
import os
import asyncio
import tempfile
from unittest import mock
from datetime import date, timedelta
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np

from data_manager.data_reader import DataReader, FieldName
from data_manager.alpha_vantage import AsyncAlphaVantageDownloader
from data_manager.exceptions import DataNotFoundError
from strategies.momentum import MomentumStrategy, Signal
from backtester import BackTester
from config import Configuration, config


class TestIntegration(unittest.TestCase):
    """Integration tests for end-to-end workflows."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test data
        self.temp_dir = tempfile.TemporaryDirectory()

        # Save original environment variables
        self.original_env = os.environ.copy()

        # Set up test environment variables
        os.environ['DATA_PICKLE_LOCATION'] = os.path.join(self.temp_dir.name, 'data_pickle')
        os.environ['DATA_JSON_LOCATION'] = os.path.join(self.temp_dir.name, 'data_json')
        os.environ['LOGS_DIR'] = os.path.join(self.temp_dir.name, 'logs')
        os.environ['ALPHA_VANTAGE_API_KEY'] = 'test_api_key'

        # Create directories
        os.makedirs(os.environ['DATA_PICKLE_LOCATION'], exist_ok=True)
        os.makedirs(os.environ['DATA_JSON_LOCATION'], exist_ok=True)
        os.makedirs(os.environ['LOGS_DIR'], exist_ok=True)

        # Sample data for testing
        dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
        self.sample_df = pd.DataFrame({
            'open': np.linspace(100, 120, len(dates)),
            'high': np.linspace(105, 125, len(dates)),
            'low': np.linspace(95, 115, len(dates)),
            'close': np.linspace(102, 122, len(dates)),
            'adjusted_close': np.linspace(102, 122, len(dates)),
            'volume': np.random.randint(1000, 10000, len(dates)),
            'dividend_amount': np.zeros(len(dates)),
            'split_coefficient': np.ones(len(dates))
        }, index=dates.date)

        # Create a mock Alpha Vantage downloader
        self.mock_downloader = mock.MagicMock(spec=AsyncAlphaVantageDownloader)

        # Create a data reader with the mock downloader
        self.data_reader = DataReader(downloader=self.mock_downloader)

    def tearDown(self):
        """Clean up after tests."""
        # Restore original environment variables
        os.environ.clear()
        os.environ.update(self.original_env)

        # Clean up temporary directory
        self.temp_dir.cleanup()

    @mock.patch('data_manager.data_reader.DataReader._load_data')
    @mock.patch('data_manager.data_reader.DataReader._save_data')
    async def test_data_retrieval_workflow(self, mock_save, mock_load):
        """Test the data retrieval workflow: configuration → data download → data processing."""
        # Set up the mocks
        mock_load.side_effect = [
            # First call: raise DataNotFoundError to trigger download
            DataNotFoundError("Data not found"),
            # Subsequent calls: return the sample data
            self.sample_df
        ]

        # Mock the downloader to return sample data
        sample_time_series_data = {
            "Meta Data": {
                "1. Information": "Daily Time Series with Adjusted close and volume",
                "2. Symbol": "AAPL",
                "3. Last Refreshed": "2023-01-31",
                "4. Output Size": "Full size",
                "5. Time Zone": "US/Eastern"
            },
            "Time Series (Daily)": {
                "2023-01-31": {
                    "1. open": "120.0000",
                    "2. high": "125.0000",
                    "3. low": "115.0000",
                    "4. close": "122.0000",
                    "5. adjusted close": "122.0000",
                    "6. volume": "9000",
                    "7. dividend amount": "0.0000",
                    "8. split coefficient": "1.0000"
                },
                # ... more data points would be here in a real response
            }
        }
        self.mock_downloader.download.return_value = sample_time_series_data

        # Call get_data to trigger the workflow
        result = await self.data_reader.get_data(
            symbol='AAPL',
            start_date=date(2023, 1, 29),
            end_date=date(2023, 1, 31)
        )

        # Verify that the downloader was called
        self.mock_downloader.download.assert_called_once_with('AAPL')

        # Verify that data was saved
        mock_save.assert_called_once()

        # Verify that we got data back
        self.assertIsInstance(result, pd.DataFrame)
        self.assertGreater(len(result), 0)

    @mock.patch('strategies.momentum.MomentumStrategy.generate_signals')
    async def test_trading_strategy_workflow(self, mock_generate_signals):
        """Test the trading strategy workflow: data retrieval → signal generation → trade execution."""
        # Create a simple momentum strategy
        strategy = MomentumStrategy(data_reader=self.data_reader)

        # Mock the data_reader.get_data method to return our sample data
        self.data_reader.get_data = mock.AsyncMock(return_value=self.sample_df)

        # Mock the generate_signals method to return buy and sell signals
        dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
        signals = pd.DataFrame({
            'signal': [Signal.HOLD.value] * 10 + [Signal.BUY.value] + [Signal.HOLD.value] * 10 + [Signal.SELL.value] + [Signal.HOLD.value] * 9
        }, index=dates.date)
        mock_generate_signals.return_value = signals

        # Create a backtester
        backtester = BackTester(
            data_reader=self.data_reader,
            initial_capital=10000,
            transaction_cost_pct=0.1
        )

        # Run the backtest
        report = await backtester.backtest(
            strategy=strategy,
            symbol='AAPL',
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 31)
        )

        # Verify that the data_reader was called
        self.data_reader.get_data.assert_called_once()

        # Verify that generate_signals was called
        mock_generate_signals.assert_called_once()

        # Verify the backtest results
        self.assertEqual(report.symbol, 'AAPL')
        self.assertEqual(len(report.trades), 1)  # One complete trade
        self.assertGreater(report.final_capital, report.initial_capital)  # Profitable trade

    @mock.patch('data_manager.data_reader.DataReader.get_data')
    @mock.patch('strategies.momentum.MomentumStrategy.generate_signals')
    async def test_compare_strategies_workflow(self, mock_generate_signals, mock_get_data):
        """Test the workflow for comparing multiple strategies."""
        # Mock the get_data method to return our sample data
        mock_get_data.return_value = self.sample_df

        # Create two strategies
        strategy1 = MomentumStrategy(data_reader=self.data_reader)
        strategy2 = MomentumStrategy(data_reader=self.data_reader)

        # Mock the generate_signals method to return different signals for each strategy
        dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')

        # Strategy 1: Buy early, sell late
        signals1 = pd.DataFrame({
            'signal': [Signal.BUY.value] + [Signal.HOLD.value] * 29 + [Signal.SELL.value]
        }, index=dates.date)

        # Strategy 2: Buy late, sell early
        signals2 = pd.DataFrame({
            'signal': [Signal.HOLD.value] * 15 + [Signal.BUY.value] + [Signal.HOLD.value] * 10 + [Signal.SELL.value] + [Signal.HOLD.value] * 4
        }, index=dates.date)

        # Set up the mock to return different signals based on the strategy
        mock_generate_signals.side_effect = lambda symbol, start_date, end_date: (
            signals1 if self == strategy1 else signals2
        )

        # Create a backtester
        backtester = BackTester(
            data_reader=self.data_reader,
            initial_capital=10000,
            transaction_cost_pct=0.1
        )

        # Run the comparison
        results = await backtester.compare_strategies(
            strategies=[strategy1, strategy2],
            symbol='AAPL',
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 31)
        )

        # Verify that get_data was called
        self.assertEqual(mock_get_data.call_count, 2)  # Once for each strategy

        # Verify that generate_signals was called for each strategy
        self.assertEqual(mock_generate_signals.call_count, 2)

        # Verify the results
        self.assertEqual(len(results), 2)
        for strategy_name, report in results.items():
            self.assertEqual(report.symbol, 'AAPL')
            self.assertEqual(len(report.trades), 1)  # One complete trade


class AsyncioTestCase(unittest.TestCase):
    """Base class for asyncio test cases."""

    def run_async(self, coro):
        """Run a coroutine in the event loop."""
        return asyncio.run(coro)


# Modify the TestIntegration class to use AsyncioTestCase
TestIntegration.__bases__ = (AsyncioTestCase,)


# Wrap async test methods to run them with run_async
for name in dir(TestIntegration):
    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestIntegration, name)):
        method = getattr(TestIntegration, name)

        def wrapper(self, method=method):
            return self.run_async(method(self))

        setattr(TestIntegration, name, wrapper)


if __name__ == '__main__':
    unittest.main()
