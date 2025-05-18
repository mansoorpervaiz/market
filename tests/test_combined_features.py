import unittest
import sys
import os
import asyncio
from datetime import date as datetime_date
from unittest import mock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np

from data_manager.data_reader import DataReader
from strategies.momentum import Signal
from strategies.top_breakout_strategy import TopBreakoutStrategy, RankingCriteria, PositionSizeMethod
from backtester import BackTester


class TestCombinedFeatures(unittest.TestCase):
    """Test cases for combined features (stop-loss and position sizing)."""

    def setUp(self):
        """Set up test fixtures."""
        self.data_reader = mock.MagicMock(spec=DataReader)

        # Create sample data for testing with a clear pattern:
        # 1. Initial period
        # 2. Breakout
        # 3. Uptrend
        # 4. Pullback (to trigger stop loss)
        # 5. Final period
        dates = pd.date_range(start='2023-01-01', end='2023-02-15', freq='D')
        num_days = len(dates)

        # Calculate segment sizes
        initial_segment = int(num_days * 0.3)  # 30% of days for initial period
        breakout_segment = int(num_days * 0.2)  # 20% of days for breakout
        uptrend_segment = int(num_days * 0.2)   # 20% of days for uptrend
        pullback_segment = int(num_days * 0.2)  # 20% of days for pullback
        final_segment = num_days - initial_segment - breakout_segment - uptrend_segment - pullback_segment

        # Create price segments
        initial_prices = np.linspace(100, 105, initial_segment)
        breakout_prices = np.linspace(105, 130, breakout_segment)
        uptrend_prices = np.linspace(130, 150, uptrend_segment)
        pullback_prices = np.linspace(150, 140, pullback_segment)  # 6.7% drop to trigger stop loss
        final_prices = np.linspace(140, 145, final_segment)

        # Combine all price segments
        prices = np.concatenate([
            initial_prices,
            breakout_prices,
            uptrend_prices,
            pullback_prices,
            final_prices
        ])

        # Create high and low prices
        highs = prices * 1.02  # 2% higher than close
        lows = prices * 0.98   # 2% lower than close

        # Create volume with a spike during breakout
        base_volume = np.ones(num_days) * 5000
        # Add volume spike during breakout period
        breakout_start = initial_segment
        breakout_end = initial_segment + breakout_segment
        base_volume[breakout_start:breakout_end] = 15000  # 3x normal volume during breakout

        # Create test dataframe
        self.test_data = pd.DataFrame({
            'open': prices * 0.99,
            'high': highs,
            'low': lows,
            'close': prices,
            'adjusted_close': prices,
            'volume': base_volume
        }, index=dates.date)

    def test_stop_loss_with_position_sizing(self):
        """Test that stop-loss and position sizing work correctly together."""
        # Configure the mock data_reader to return the test data
        async def mock_get_data(*args, **kwargs):
            return self.test_data.copy()

        self.data_reader.get_data = mock_get_data

        # For get_data_sync method (used by TopBreakoutStrategy for stop loss)
        def mock_get_data_sync(symbol, start_date, end_date):
            mask = (self.test_data.index >= start_date) & (self.test_data.index <= end_date)
            return self.test_data.loc[mask]

        self.data_reader.get_data_sync = mock_get_data_sync

        # Mock the symbol manager to return a list of symbols
        class MockSymbolManager:
            def get_symbols_space_separated(self):
                return ['AAPL', 'MSFT', 'GOOG']

        # Create the strategy with both trailing stop and position sizing enabled
        strategy = TopBreakoutStrategy(
            data_reader=self.data_reader,
            avg_period=5,            # Shorter period for testing
            top_percent=50,          # Higher percentage to ensure our test symbol is selected
            ranking_criteria=RankingCriteria.COMBINED_SCORE,
            rebalance_days=7,
            use_trailing_stop=True,
            trailing_stop_pct=2.0,   # 2% trailing stop
            position_size_method=PositionSizeMethod.VOLATILITY_ADJUSTED
        )

        # Replace the symbol manager with our mock
        strategy.symbol_manager = MockSymbolManager()

        # Create a backtester
        backtester = BackTester(
            data_reader=self.data_reader,
            initial_capital=10000,
            transaction_cost_pct=0.1
        )

        # Run the backtest
        start_date = datetime_date(2023, 1, 15)
        end_date = datetime_date(2023, 2, 10)
        report = asyncio.run(backtester.backtest(
            strategy=strategy,
            symbol='AAPL',
            start_date=start_date,
            end_date=end_date
        ))

        # Verify the backtest results
        self.assertEqual(report.symbol, 'AAPL')
        self.assertGreaterEqual(len(report.trades), 1)  # At least one trade

        # Verify that position sizing was applied
        # The exact position size depends on the volatility, but the final capital should be different
        # from what we would expect if 100% of capital was allocated
        self.assertNotEqual(report.final_capital, report.initial_capital)

        # Verify that stop-loss was triggered
        # If stop-loss was triggered, there should be a sell signal after a buy signal
        # and before the end of the test period
        signals = asyncio.run(strategy.generate_signals(
            symbol='AAPL',
            start_date=start_date,
            end_date=end_date
        ))

        buy_signals = signals[signals['signal'] == Signal.BUY.value]
        if not buy_signals.empty:
            # Find the first buy signal
            first_buy_idx = signals.index.get_indexer([buy_signals.index[0]])[0]

            # Get all signals after the first buy signal
            sells_after_buy = signals.iloc[first_buy_idx+1:]

            self.assertTrue((sells_after_buy['signal'] == Signal.SELL.value).any(),
                           "No SELL signals were generated after BUY signals (stop-loss not triggered)")

    def test_edge_cases(self):
        """Test edge cases for stop-loss and position sizing."""
        # Configure the mock data_reader to return the test data
        async def mock_get_data(*args, **kwargs):
            return self.test_data.copy()

        self.data_reader.get_data = mock_get_data

        # For get_data_sync method (used by TopBreakoutStrategy for stop loss)
        def mock_get_data_sync(symbol, start_date, end_date):
            mask = (self.test_data.index >= start_date) & (self.test_data.index <= end_date)
            return self.test_data.loc[mask]

        self.data_reader.get_data_sync = mock_get_data_sync

        # Mock the symbol manager to return a list of symbols
        class MockSymbolManager:
            def get_symbols_space_separated(self):
                return ['AAPL', 'MSFT', 'GOOG']

        # Test cases for different combinations of parameters
        test_cases = [
            # Test case 1: Stop-loss disabled, position sizing enabled
            {
                'use_trailing_stop': False,
                'trailing_stop_pct': 2.0,
                'position_size_method': PositionSizeMethod.EQUAL_WEIGHT
            },
            # Test case 2: Stop-loss enabled with tight stop, position sizing enabled
            {
                'use_trailing_stop': True,
                'trailing_stop_pct': 1.0,  # Tighter stop
                'position_size_method': PositionSizeMethod.EQUAL_WEIGHT
            },
            # Test case 3: Stop-loss enabled with loose stop, position sizing enabled
            {
                'use_trailing_stop': True,
                'trailing_stop_pct': 5.0,  # Looser stop
                'position_size_method': PositionSizeMethod.EQUAL_WEIGHT
            },
            # Test case 4: Stop-loss enabled, position sizing with performance-based method
            {
                'use_trailing_stop': True,
                'trailing_stop_pct': 2.0,
                'position_size_method': PositionSizeMethod.PERFORMANCE_BASED
            }
        ]

        for i, params in enumerate(test_cases):
            # Create the strategy with the current parameters
            strategy = TopBreakoutStrategy(
                data_reader=self.data_reader,
                avg_period=5,            # Shorter period for testing
                top_percent=50,          # Higher percentage to ensure our test symbol is selected
                ranking_criteria=RankingCriteria.COMBINED_SCORE,
                rebalance_days=7,
                use_trailing_stop=params['use_trailing_stop'],
                trailing_stop_pct=params['trailing_stop_pct'],
                position_size_method=params['position_size_method']
            )

            # Replace the symbol manager with our mock
            strategy.symbol_manager = MockSymbolManager()

            # Generate signals
            start_date = datetime_date(2023, 1, 15)
            end_date = datetime_date(2023, 2, 10)
            signals = asyncio.run(strategy.generate_signals(
                symbol='AAPL',
                start_date=start_date,
                end_date=end_date
            ))

            # Verify that signals were generated
            self.assertIsInstance(signals, pd.DataFrame)
            self.assertIn('signal', signals.columns)
            self.assertIn('position_size', signals.columns)
            self.assertTrue((signals['signal'].isin([Signal.BUY.value, Signal.SELL.value, Signal.HOLD.value])).all())

            # Verify that at least one buy signal was generated
            self.assertTrue((signals['signal'] == Signal.BUY.value).any(),
                           f"No BUY signals were generated for test case {i+1}")

            # Verify that position sizes are set for buy signals
            buy_signals = signals[signals['signal'] == Signal.BUY.value]
            self.assertTrue((buy_signals['position_size'] > 0).all(),
                           f"Position sizes not set correctly for test case {i+1}")

            # If stop-loss is enabled, verify that it works as expected
            if params['use_trailing_stop']:
                # If there's a buy signal, there should be a sell signal after it
                # (either due to stop-loss or rebalancing)
                if not buy_signals.empty:
                    # Find the first buy signal
                    first_buy_idx = signals.index.get_indexer([buy_signals.index[0]])[0]

                    # Get all signals after the first buy signal
                    sells_after_buy = signals.iloc[first_buy_idx+1:]

                    # With a tighter stop (1.0%), we expect a sell signal to be generated
                    # With a looser stop (5.0%), we might not see a sell signal in our test data
                    if params['trailing_stop_pct'] <= 2.0:
                        self.assertTrue((sells_after_buy['signal'] == Signal.SELL.value).any(),
                                      f"No SELL signals were generated after BUY signals for test case {i+1}")

    def test_volatility_filter(self):
        """Test that the volatility filter correctly filters out excessively volatile stocks."""
        # Create test data with different volatility levels for multiple stocks
        dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
        num_days = len(dates)

        # Create base price data
        base_prices = np.linspace(100, 120, num_days)

        # Create test data for multiple stocks with different volatility levels
        stock_data = {}

        # Stock 1: Low volatility (should pass filter)
        low_vol_prices = base_prices + np.random.normal(0, 1, num_days)  # Small random fluctuations
        stock_data['LOW_VOL'] = pd.DataFrame({
            'open': low_vol_prices * 0.99,
            'high': low_vol_prices * 1.01,
            'low': low_vol_prices * 0.99,
            'close': low_vol_prices,
            'adjusted_close': low_vol_prices,
            'volume': np.random.randint(1000, 10000, num_days)
        }, index=dates.date)

        # Stock 2: Medium volatility (should pass filter)
        med_vol_prices = base_prices + np.random.normal(0, 3, num_days)  # Medium random fluctuations
        stock_data['MED_VOL'] = pd.DataFrame({
            'open': med_vol_prices * 0.98,
            'high': med_vol_prices * 1.03,
            'low': med_vol_prices * 0.97,
            'close': med_vol_prices,
            'adjusted_close': med_vol_prices,
            'volume': np.random.randint(1000, 10000, num_days)
        }, index=dates.date)

        # Stock 3: High volatility (should be filtered out)
        high_vol_prices = base_prices + np.random.normal(0, 8, num_days)  # Large random fluctuations
        stock_data['HIGH_VOL'] = pd.DataFrame({
            'open': high_vol_prices * 0.95,
            'high': high_vol_prices * 1.08,
            'low': high_vol_prices * 0.92,
            'close': high_vol_prices,
            'adjusted_close': high_vol_prices,
            'volume': np.random.randint(1000, 10000, num_days)
        }, index=dates.date)

        # Configure the mock data_reader to return different data based on the symbol
        async def mock_get_data(symbol, *args, **kwargs):
            if symbol in stock_data:
                return stock_data[symbol].copy()
            return pd.DataFrame()  # Empty DataFrame for unknown symbols

        self.data_reader.get_data = mock_get_data

        # For get_data_sync method
        def mock_get_data_sync(symbol, start_date, end_date):
            if symbol in stock_data:
                mask = (stock_data[symbol].index >= start_date) & (stock_data[symbol].index <= end_date)
                return stock_data[symbol].loc[mask]
            return pd.DataFrame()

        self.data_reader.get_data_sync = mock_get_data_sync

        # Mock the symbol manager to return our test symbols
        class MockSymbolManager:
            def get_symbols_space_separated(self):
                return ['LOW_VOL', 'MED_VOL', 'HIGH_VOL']

        # Test cases for different volatility filter configurations
        test_cases = [
            # Test case 1: Volatility filter enabled with default threshold
            {
                'use_volatility_filter': True,
                'max_atr_ratio': 5.0,  # Default threshold
                'expected_symbols': ['LOW_VOL']  # Only LOW_VOL should pass the filter
            },
            # Test case 2: Volatility filter enabled with lower threshold
            {
                'use_volatility_filter': True,
                'max_atr_ratio': 2.0,  # Lower threshold
                'expected_symbols': []  # No symbols should pass (LOW_VOL has ATR ratio ~2.02%)
            },
            # Test case 3: Volatility filter disabled
            {
                'use_volatility_filter': False,
                'max_atr_ratio': 5.0,  # Doesn't matter when filter is disabled
                'expected_symbols': ['LOW_VOL', 'MED_VOL', 'HIGH_VOL']  # All symbols should be included
            },
            # Test case 4: Extreme case - all stocks filtered out
            {
                'use_volatility_filter': True,
                'max_atr_ratio': 0.5,  # Very low threshold that no stock can pass
                'expected_symbols': []  # No symbols should pass
            }
        ]

        for i, params in enumerate(test_cases):
            # Create the strategy with the current parameters
            strategy = TopBreakoutStrategy(
                data_reader=self.data_reader,
                avg_period=5,            # Shorter period for testing
                top_percent=100,         # Select all stocks that pass the filter
                ranking_criteria=RankingCriteria.COMBINED_SCORE,
                rebalance_days=7,
                use_trailing_stop=True,
                trailing_stop_pct=2.0,
                position_size_method=PositionSizeMethod.EQUAL_WEIGHT,
                use_volatility_filter=params['use_volatility_filter'],
                max_atr_ratio=params['max_atr_ratio']
            )

            # Replace the symbol manager with our mock
            strategy.symbol_manager = MockSymbolManager()

            # Run the strategy's _select_top_symbols method to get the selected symbols
            start_date = datetime_date(2023, 1, 15)
            selected_symbols = asyncio.run(strategy._select_top_symbols(start_date))

            # Verify that the correct symbols were selected based on the volatility filter
            self.assertEqual(set(selected_symbols), set(params['expected_symbols']),
                           f"Test case {i+1}: Expected {params['expected_symbols']}, got {selected_symbols}")

            # For the first test case (default settings), also test the full signal generation
            if i == 0:
                # Generate signals for each symbol
                for symbol in ['LOW_VOL', 'MED_VOL', 'HIGH_VOL']:
                    end_date = datetime_date(2023, 1, 30)
                    signals = asyncio.run(strategy.generate_signals(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date
                    ))

                    # Verify that signals were generated
                    self.assertIsInstance(signals, pd.DataFrame)
                    self.assertIn('signal', signals.columns)

                    # Verify that buy signals are only generated for symbols that pass the filter
                    if symbol in params['expected_symbols']:
                        # Should have at least one buy signal
                        self.assertTrue((signals['signal'] == Signal.BUY.value).any(),
                                      f"No BUY signals were generated for {symbol} which should pass the filter")
                    else:
                        # Should not have any buy signals
                        self.assertFalse((signals['signal'] == Signal.BUY.value).any(),
                                       f"BUY signals were generated for {symbol} which should be filtered out")

    def test_volatility_filter_with_other_features(self):
        """Test that the volatility filter works correctly when combined with other features."""
        # Create test data with different volatility levels for multiple stocks
        dates = pd.date_range(start='2023-01-01', end='2023-02-15', freq='D')
        num_days = len(dates)

        # Calculate segment sizes for price patterns
        initial_segment = int(num_days * 0.3)  # 30% of days for initial period
        breakout_segment = int(num_days * 0.2)  # 20% of days for breakout
        uptrend_segment = int(num_days * 0.2)   # 20% of days for uptrend
        pullback_segment = int(num_days * 0.2)  # 20% of days for pullback
        final_segment = num_days - initial_segment - breakout_segment - uptrend_segment - pullback_segment

        # Create price segments
        initial_prices = np.linspace(100, 105, initial_segment)
        breakout_prices = np.linspace(105, 130, breakout_segment)
        uptrend_prices = np.linspace(130, 150, uptrend_segment)
        pullback_prices = np.linspace(150, 140, pullback_segment)  # 6.7% drop to trigger stop loss
        final_prices = np.linspace(140, 145, final_segment)

        # Combine all price segments
        base_prices = np.concatenate([
            initial_prices,
            breakout_prices,
            uptrend_prices,
            pullback_prices,
            final_prices
        ])

        # Create test data for multiple stocks with different volatility levels
        stock_data = {}

        # Stock 1: Low volatility (should pass filter)
        # Add small random fluctuations to create low volatility
        low_vol_prices = base_prices * (1 + np.random.normal(0, 0.01, num_days))
        highs_low_vol = low_vol_prices * 1.01  # 1% higher than close
        lows_low_vol = low_vol_prices * 0.99   # 1% lower than close

        stock_data['LOW_VOL'] = pd.DataFrame({
            'open': low_vol_prices * 0.995,
            'high': highs_low_vol,
            'low': lows_low_vol,
            'close': low_vol_prices,
            'adjusted_close': low_vol_prices,
            'volume': np.random.randint(1000, 10000, num_days)
        }, index=dates.date)

        # Stock 2: High volatility (should be filtered out)
        # Add large random fluctuations to create high volatility
        high_vol_prices = base_prices * (1 + np.random.normal(0, 0.05, num_days))
        highs_high_vol = high_vol_prices * 1.08  # 8% higher than close
        lows_high_vol = high_vol_prices * 0.92   # 8% lower than close

        stock_data['HIGH_VOL'] = pd.DataFrame({
            'open': high_vol_prices * 0.98,
            'high': highs_high_vol,
            'low': lows_high_vol,
            'close': high_vol_prices,
            'adjusted_close': high_vol_prices,
            'volume': np.random.randint(1000, 10000, num_days)
        }, index=dates.date)

        # Configure the mock data_reader to return different data based on the symbol
        async def mock_get_data(symbol, *args, **kwargs):
            if symbol in stock_data:
                return stock_data[symbol].copy()
            return pd.DataFrame()  # Empty DataFrame for unknown symbols

        self.data_reader.get_data = mock_get_data

        # For get_data_sync method
        def mock_get_data_sync(symbol, start_date, end_date):
            if symbol in stock_data:
                mask = (stock_data[symbol].index >= start_date) & (stock_data[symbol].index <= end_date)
                return stock_data[symbol].loc[mask]
            return pd.DataFrame()

        self.data_reader.get_data_sync = mock_get_data_sync

        # Mock the symbol manager to return our test symbols
        class MockSymbolManager:
            def get_symbols_space_separated(self):
                return ['LOW_VOL', 'HIGH_VOL']

        # Create the strategy with volatility filter, trailing stop, and position sizing
        strategy = TopBreakoutStrategy(
            data_reader=self.data_reader,
            avg_period=5,            # Shorter period for testing
            top_percent=100,         # Select all stocks that pass the filter
            ranking_criteria=RankingCriteria.COMBINED_SCORE,
            rebalance_days=7,
            use_trailing_stop=True,
            trailing_stop_pct=2.0,
            position_size_method=PositionSizeMethod.VOLATILITY_ADJUSTED,
            use_volatility_filter=True,
            max_atr_ratio=5.0        # Default threshold
        )

        # Replace the symbol manager with our mock
        strategy.symbol_manager = MockSymbolManager()

        # Create a backtester
        backtester = BackTester(
            data_reader=self.data_reader,
            initial_capital=10000,
            transaction_cost_pct=0.1
        )

        # Run the backtest for both symbols
        start_date = datetime_date(2023, 1, 15)
        end_date = datetime_date(2023, 2, 10)

        # Run backtest for LOW_VOL (should pass filter)
        low_vol_report = asyncio.run(backtester.backtest(
            strategy=strategy,
            symbol='LOW_VOL',
            start_date=start_date,
            end_date=end_date
        ))

        # Run backtest for HIGH_VOL (should be filtered out)
        high_vol_report = asyncio.run(backtester.backtest(
            strategy=strategy,
            symbol='HIGH_VOL',
            start_date=start_date,
            end_date=end_date
        ))

        # Verify that LOW_VOL has trades (passes filter)
        self.assertGreater(len(low_vol_report.trades), 0,
                         "No trades were generated for LOW_VOL which should pass the filter")

        # Verify that HIGH_VOL has no trades (filtered out)
        self.assertEqual(len(high_vol_report.trades), 0,
                       "Trades were generated for HIGH_VOL which should be filtered out")

        # Verify that position sizing was applied for LOW_VOL
        if len(low_vol_report.trades) > 0:
            # Check that the final capital is different from what we would expect if 100% of capital was allocated
            # This is an indirect way to verify that position sizing was applied
            self.assertNotEqual(low_vol_report.final_capital, low_vol_report.initial_capital,
                              "Final capital should be different from initial capital, indicating position sizing was applied")

        # Verify that trailing stop works for LOW_VOL
        # Generate signals to check for sell signals
        low_vol_signals = asyncio.run(strategy.generate_signals(
            symbol='LOW_VOL',
            start_date=start_date,
            end_date=end_date
        ))

        # If there are buy signals, there should be sell signals due to trailing stop
        buy_signals = low_vol_signals[low_vol_signals['signal'] == Signal.BUY.value]
        if not buy_signals.empty:
            # Find the first buy signal
            first_buy_idx = low_vol_signals.index.get_indexer([buy_signals.index[0]])[0]

            # Get all signals after the first buy signal
            sells_after_buy = low_vol_signals.iloc[first_buy_idx+1:]

            # There should be at least one sell signal after a buy signal
            self.assertTrue((sells_after_buy['signal'] == Signal.SELL.value).any(),
                          "No SELL signals were generated after BUY signals for LOW_VOL (trailing stop not working)")


class AsyncioTestCase(unittest.TestCase):
    """Base class for asyncio test cases."""

    def run_async(self, coro):
        """Run a coroutine in the event loop."""
        return asyncio.run(coro)


# Modify the TestCombinedFeatures class to use AsyncioTestCase
TestCombinedFeatures.__bases__ = (AsyncioTestCase,)


# Wrap async test methods to run them with run_async
for name in dir(TestCombinedFeatures):
    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestCombinedFeatures, name)):
        method = getattr(TestCombinedFeatures, name)

        def wrapper(self, method=method):
            return self.run_async(method(self))

        setattr(TestCombinedFeatures, name, wrapper)


if __name__ == '__main__':
    unittest.main()
