import sys
import os
import asyncio
import pandas as pd
import numpy as np
from datetime import date as datetime_date
from unittest import mock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_manager.data_reader import DataReader
from strategies.top_breakout_strategy import TopBreakoutStrategy, RankingCriteria, PositionSizeMethod

async def debug_volatility_filter():
    # Create a mock data reader
    data_reader = mock.MagicMock(spec=DataReader)

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

    data_reader.get_data = mock_get_data

    # For get_data_with_lookback method
    async def mock_get_data_with_lookback(symbol, start_date, end_date, lookback_days):
        if symbol in stock_data:
            df = stock_data[symbol].copy()

            # Debug: Add ATR calculation directly to the dataframe
            if symbol == 'HIGH_VOL':
                print(f"\nPreparing data for {symbol} in get_data_with_lookback")
                # Calculate True Range
                df['tr'] = np.maximum(
                    df['high'] - df['low'],
                    np.maximum(
                        abs(df['high'] - df['close'].shift(1)),
                        abs(df['low'] - df['close'].shift(1))
                    )
                )
                # Calculate ATR
                df['atr'] = df['tr'].rolling(window=strategy.atr_period).mean()
                # Calculate ATR ratio as percentage of price
                df['atr_ratio'] = df['atr'] / df['close'] * 100

                # Print the last row to see if ATR ratio is calculated
                print("Last row of data for HIGH_VOL:")
                print(df.iloc[-1])

            return df
        return pd.DataFrame()

    data_reader.get_data_with_lookback = mock_get_data_with_lookback

    # Mock the symbol manager to return our test symbols
    class MockSymbolManager:
        def get_symbols_space_separated(self):
            return ['LOW_VOL', 'MED_VOL', 'HIGH_VOL']

    # Create the strategy with volatility filter enabled
    strategy = TopBreakoutStrategy(
        data_reader=data_reader,
        avg_period=5,            # Shorter period for testing
        top_percent=100,         # Select all stocks that pass the filter
        ranking_criteria=RankingCriteria.COMBINED_SCORE,
        rebalance_days=7,
        use_trailing_stop=True,
        trailing_stop_pct=2.0,
        position_size_method=PositionSizeMethod.EQUAL_WEIGHT,
        use_volatility_filter=True,
        max_atr_ratio=5.0        # Default threshold
    )

    # Replace the symbol manager with our mock
    strategy.symbol_manager = MockSymbolManager()

    # Override the _calculate_metrics method to add debug prints
    original_calculate_metrics = strategy._calculate_metrics

    async def debug_calculate_metrics(symbols, current_date):
        print("\nDebug: Inside _calculate_metrics")
        print(f"Symbols: {symbols}")
        print(f"Current date: {current_date}")

        # Call the original method
        metrics_df = await original_calculate_metrics(symbols, current_date)

        # Print the metrics DataFrame
        print("\nDebug: Metrics DataFrame from _calculate_metrics:")
        print(metrics_df)

        # Check if atr_ratio is in the DataFrame
        if 'atr_ratio' in metrics_df.columns:
            print("\nDebug: atr_ratio is in the metrics DataFrame")
        else:
            print("\nDebug: atr_ratio is NOT in the metrics DataFrame")

        return metrics_df

    # Replace the method with our debug version
    strategy._calculate_metrics = debug_calculate_metrics

    # Calculate metrics for all symbols
    current_date = datetime_date(2023, 1, 15)
    symbols = strategy.symbol_manager.get_symbols_space_separated()

    # Debug: Print the raw data for HIGH_VOL to check ATR calculation
    print("Raw data for HIGH_VOL:")
    high_vol_data = stock_data['HIGH_VOL'].head()
    print(high_vol_data)

    # Debug: Manually calculate ATR for HIGH_VOL
    print("\nManually calculating ATR for HIGH_VOL:")
    df = stock_data['HIGH_VOL'].copy()
    # Calculate True Range
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    # Calculate ATR
    df['atr'] = df['tr'].rolling(window=strategy.atr_period).mean()
    # Calculate ATR ratio as percentage of price
    df['atr_ratio'] = df['atr'] / df['close'] * 100
    print(df[['close', 'tr', 'atr', 'atr_ratio']].head(20))

    # Calculate metrics for all symbols
    metrics_df = await strategy._calculate_metrics(symbols, current_date)

    # Print the metrics for each symbol
    print("\nMetrics for each symbol:")
    for symbol in symbols:
        symbol_metrics = metrics_df[metrics_df['symbol'] == symbol]
        print(f"\n{symbol}:")
        for col in symbol_metrics.columns:
            print(f"  {col}: {symbol_metrics[col].values[0]}")

    # Print which symbols would be selected
    selected_symbols = await strategy._select_top_symbols(current_date)
    print(f"\nSelected symbols: {selected_symbols}")

if __name__ == "__main__":
    asyncio.run(debug_volatility_filter())
