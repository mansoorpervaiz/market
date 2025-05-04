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
from strategies.momentum import (
    Signal,
    MomentumStrategy,
    RateOfChangeStrategy,
    MovingAverageCrossoverStrategy,
    RSIStrategy
)


class TestMomentumStrategies(unittest.TestCase):
    """Test cases for momentum trading strategies."""

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

    def test_rate_of_change_strategy(self):
        """Test the Rate of Change strategy."""
        # Configure the mock data_reader to return the sample data directly
        async def mock_get_data(*args, **kwargs):
            return self.sample_data.copy()

        self.data_reader.get_data = mock_get_data

        # Create the strategy
        strategy = RateOfChangeStrategy(
            data_reader=self.data_reader,
            n_days=5,
            threshold_pct=2,
            sell_threshold_pct=-2
        )

        # Run the strategy
        start_date = date(2023, 1, 10)
        end_date = date(2023, 1, 30)
        signals = asyncio.run(strategy.generate_signals(
            symbol='AAPL',
            start_date=start_date,
            end_date=end_date
        ))

        # Verify the results
        self.assertIsInstance(signals, pd.DataFrame)
        self.assertIn('signal', signals.columns)
        self.assertTrue((signals['signal'].isin([Signal.BUY.value, Signal.SELL.value, Signal.HOLD.value])).all())

    def test_moving_average_crossover_strategy(self):
        """Test the Moving Average Crossover strategy."""
        # Create data with a crossover
        dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
        prices = np.concatenate([
            np.linspace(100, 90, 15),  # Downtrend
            np.linspace(90, 110, 16)   # Uptrend
        ])

        crossover_data = pd.DataFrame({
            'open': prices,
            'high': prices + 5,
            'low': prices - 5,
            'close': prices,
            'adjusted_close': prices,
            'volume': np.random.randint(1000, 10000, len(dates))
        }, index=dates.date)

        # Configure the mock data_reader to return the crossover data directly
        async def mock_get_data(*args, **kwargs):
            return crossover_data

        self.data_reader.get_data = mock_get_data

        # Create the strategy
        strategy = MovingAverageCrossoverStrategy(
            data_reader=self.data_reader,
            short_window=5,
            long_window=10
        )

        # Run the strategy
        start_date = date(2023, 1, 10)
        end_date = date(2023, 1, 30)
        signals = asyncio.run(strategy.generate_signals(
            symbol='AAPL',
            start_date=start_date,
            end_date=end_date
        ))

        # Verify the results
        self.assertIsInstance(signals, pd.DataFrame)
        self.assertIn('signal', signals.columns)
        self.assertTrue((signals['signal'].isin([Signal.BUY.value, Signal.SELL.value, Signal.HOLD.value])).all())

        # There should be at least one buy signal after the crossover
        self.assertTrue((signals['signal'] == Signal.BUY.value).any())

    def test_rsi_strategy(self):
        """Test the RSI strategy."""
        # Create data with overbought and oversold conditions
        dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')

        # Create a price series with clear up and down movements
        prices = []
        current_price = 100

        # First create a downtrend to trigger oversold
        for _ in range(10):
            current_price *= 0.98  # 2% drop
            prices.append(current_price)

        # Then create an uptrend to trigger overbought
        for _ in range(10):
            current_price *= 1.03  # 3% rise
            prices.append(current_price)

        # Add some random movement
        for _ in range(11):
            current_price *= np.random.uniform(0.99, 1.01)
            prices.append(current_price)

        rsi_test_data = pd.DataFrame({
            'open': prices,
            'high': [p * 1.01 for p in prices],
            'low': [p * 0.99 for p in prices],
            'close': prices,
            'adjusted_close': prices,
            'volume': np.random.randint(1000, 10000, len(dates))
        }, index=dates.date)

        # Configure the mock data_reader to return the RSI test data directly
        async def mock_get_data(*args, **kwargs):
            return rsi_test_data

        self.data_reader.get_data = mock_get_data

        # Create the strategy
        strategy = RSIStrategy(
            data_reader=self.data_reader,
            window=5,  # Shorter window for testing
            oversold=30,
            overbought=70
        )

        # Run the strategy
        start_date = date(2023, 1, 5)
        end_date = date(2023, 1, 30)
        signals = asyncio.run(strategy.generate_signals(
            symbol='AAPL',
            start_date=start_date,
            end_date=end_date
        ))

        # Verify the results
        self.assertIsInstance(signals, pd.DataFrame)
        self.assertIn('signal', signals.columns)
        self.assertTrue((signals['signal'].isin([Signal.BUY.value, Signal.SELL.value, Signal.HOLD.value])).all())


if __name__ == '__main__':
    unittest.main()
