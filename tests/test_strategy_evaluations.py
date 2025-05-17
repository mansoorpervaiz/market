"""
# Strategy Evaluation Tests

This file contains tests and evaluations of various trading strategies that were
previously commented out in example_momentum_trading.py. These evaluations document
why certain strategies don't work well and provide experimental code for testing.

Copyright (c) 2025 Mansoor Pervaiz
All rights reserved.
"""

import asyncio
import pandas as pd
from datetime import date

from data_manager.data_reader import DataReader
from strategies.momentum import (
    RateOfChangeStrategy,
    MovingAverageCrossoverStrategy,
    RSIStrategy, 
    BreakoutStrategy
)
from backtester import BackTester


async def test_moving_average_crossover():
    """
    Test the MovingAverageCrossover strategy.
    
    Notes on why this strategy doesn't work well:
    - MovingAverageCrossover is not a tradable strategy in its current form.
    - Even though MA crossover systems are popular, they:
      - Work better on commodities or FX, not equities.
      - Need trend filters (ADX, slope filters, volume filters).
      - Often benefit from volatility or momentum confirmation.
    """
    # Get SP500 tickers
    sp500_file = "data/SP500.csv"
    
    # Initialize components
    data_reader = DataReader()
    strategy = MovingAverageCrossoverStrategy(
        data_reader=data_reader,
        short_window=20,
        long_window=50
    )
    backtester = BackTester(
        data_reader=data_reader,
        initial_capital=10000,
        transaction_cost_pct=0.1
    )
    
    # Define test period
    start_date = date(2020, 1, 1)
    end_date = date(2022, 12, 31)
    
    # Run backtest on a sample ticker
    symbol = "AAPL"  # Example ticker
    report = await backtester.backtest(
        strategy=strategy,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date
    )
    
    # Print results
    print(f"\nMovingAverageCrossover Strategy Results for {symbol}:")
    for key, value in report.summary().items():
        print(f"{key}: {value}")
    
    return report


async def test_rsi_strategy():
    """
    Test the RSI strategy.
    
    Notes on why this strategy doesn't work well:
    1. Only 41 out of 81000 tests were "good"
       - That's 0.05% success rate — effectively noise.
       - Most configurations had Sharpe < 0, meaning the strategy underperformed risk-free returns.
    
    2. Returns were driven by a few lucky trades
       - Even the best configurations often had fewer than 20 trades in 10 years.
       - This isn't repeatable — it's statistically flimsy.
    
    3. Highly parameter-sensitive
       - Tiny changes in RSI window or thresholds led to wildly different outcomes.
       - This is a sign of overfitting, not robust alpha.
    
    4. Drawdowns remain high
       - 20–30% drawdowns for modest returns are unattractive for short-term trading.
       - You'd get better risk-adjusted returns just holding SPY.
    """
    # Initialize components
    data_reader = DataReader()
    strategy = RSIStrategy(
        data_reader=data_reader,
        window=14,
        oversold=30,
        overbought=70,
        use_trend_filter=True,
        ma_period=200
    )
    backtester = BackTester(
        data_reader=data_reader,
        initial_capital=10000,
        transaction_cost_pct=0.1
    )
    
    # Define test period
    start_date = date(2020, 1, 1)
    end_date = date(2022, 12, 31)
    
    # Run backtest on a sample ticker
    symbol = "AAPL"  # Example ticker
    report = await backtester.backtest(
        strategy=strategy,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date
    )
    
    # Print results
    print(f"\nRSI Strategy Results for {symbol}:")
    for key, value in report.summary().items():
        print(f"{key}: {value}")
    
    return report


async def test_rate_of_change_strategy():
    """
    Test the Rate of Change strategy.
    
    Notes on why this strategy doesn't work well:
    - Is not profitable or robust across a broad universe.
    - Has very few consistently winning tickers.
    - Underperforms passive investing (e.g., SPY buy-and-hold).
    - Shows signs of overfitting + signal noise.
    """
    # Initialize components
    data_reader = DataReader()
    strategy = RateOfChangeStrategy(
        data_reader=data_reader,
        n_days=14,
        threshold_pct=5,
        sell_threshold_pct=-3
    )
    backtester = BackTester(
        data_reader=data_reader,
        initial_capital=10000,
        transaction_cost_pct=0.1
    )
    
    # Define test period
    start_date = date(2020, 1, 1)
    end_date = date(2022, 12, 31)
    
    # Run backtest on a sample ticker
    symbol = "AAPL"  # Example ticker
    report = await backtester.backtest(
        strategy=strategy,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date
    )
    
    # Print results
    print(f"\nRate of Change Strategy Results for {symbol}:")
    for key, value in report.summary().items():
        print(f"{key}: {value}")
    
    return report


async def test_breakout_strategy():
    """
    Test the Breakout strategy.
    """
    # Initialize components
    data_reader = DataReader()
    strategy = BreakoutStrategy(
        data_reader=data_reader
    )
    backtester = BackTester(
        data_reader=data_reader,
        initial_capital=10000,
        transaction_cost_pct=0.1
    )
    
    # Define test period
    start_date = date(2020, 1, 1)
    end_date = date(2022, 12, 31)
    
    # Run backtest on a sample ticker
    symbol = "AAPL"  # Example ticker
    report = await backtester.backtest(
        strategy=strategy,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date
    )
    
    # Print results
    print(f"\nBreakout Strategy Results for {symbol}:")
    for key, value in report.summary().items():
        print(f"{key}: {value}")
    
    return report


async def test_compare_strategies():
    """
    Compare multiple trading strategies across a sample ticker.
    """
    # Initialize the data reader
    data_reader = DataReader()

    # Create strategies
    roc_strategy = RateOfChangeStrategy(
        data_reader=data_reader,
        n_days=10,
        threshold_pct=3,
        sell_threshold_pct=-3
    )

    ma_strategy = MovingAverageCrossoverStrategy(
        data_reader=data_reader,
        short_window=20,
        long_window=50
    )

    rsi_strategy = RSIStrategy(
        data_reader=data_reader,
        window=14,
        oversold=30,
        overbought=70
    )

    # Initialize the backtester
    backtester = BackTester(
        data_reader=data_reader,
        initial_capital=10000,
        transaction_cost_pct=0.1
    )

    # Define the backtest parameters
    start_date = date(2020, 1, 1)
    end_date = date(2022, 12, 31)
    symbol = "AAPL"  # Example ticker

    # Run the comparison
    results = await backtester.compare_strategies(
        strategies=[roc_strategy, ma_strategy, rsi_strategy],
        symbol=symbol,
        start_date=start_date,
        end_date=end_date
    )

    # Print the results
    print(f"\nStrategy Comparison for {symbol}:")
    for strategy_name, report in results.items():
        print(f"\n{strategy_name}:")
        print(f"Total Return: {report.total_return:.2f}%")
        print(f"Annualized Return: {report.annualized_return:.2f}%")
        print(f"Sharpe Ratio: {report.sharpe_ratio:.2f}")
        print(f"Max Drawdown: {report.max_drawdown:.2f}%")
        print(f"Number of Trades: {len(report.trades)}")

    return results


async def test_compare_to_benchmark():
    """
    Compare a strategy to a benchmark for a sample ticker.
    """
    # Initialize the data reader
    data_reader = DataReader()

    # Create a strategy
    ma_strategy = MovingAverageCrossoverStrategy(
        data_reader=data_reader,
        short_window=20,
        long_window=50
    )

    # Initialize the backtester
    backtester = BackTester(
        data_reader=data_reader,
        initial_capital=10000,
        transaction_cost_pct=0.1
    )

    # Define the backtest parameters
    benchmark_symbol = 'SPY'
    start_date = date(2020, 1, 1)
    end_date = date(2022, 12, 31)
    symbol = "AAPL"  # Example ticker

    # Run the comparison
    strategy_report, benchmark_data = await backtester.compare_to_benchmark(
        strategy=ma_strategy,
        symbol=symbol,
        benchmark_symbol=benchmark_symbol,
        start_date=start_date,
        end_date=end_date
    )

    # Print the results
    print(f"\nStrategy vs Benchmark for {symbol}:")
    print(f"Strategy Total Return: {strategy_report.total_return:.2f}%")

    # Calculate benchmark return
    benchmark_return = ((benchmark_data.iloc[-1] - benchmark_data.iloc[0]) / benchmark_data.iloc[0]) * 100
    print(f"Benchmark Total Return: {benchmark_return:.2f}%")

    return strategy_report, benchmark_data


async def run_all_tests():
    """Run all strategy evaluation tests."""
    print("Running strategy evaluation tests...")
    
    await test_moving_average_crossover()
    await test_rsi_strategy()
    await test_rate_of_change_strategy()
    await test_breakout_strategy()
    await test_compare_strategies()
    await test_compare_to_benchmark()
    
    print("\nAll tests completed.")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
"""