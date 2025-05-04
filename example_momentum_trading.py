#!/usr/bin/env python3
# Copyright (c) 2025 Mansoor Pervaiz
# All rights reserved.
#
# This file is part of a proprietary software project.
# Unauthorized copying, distribution, modification, or use of this file,
# via any medium, is strictly prohibited unless explicit permission is granted
# by the author.
#
# For licensing inquiries, contact: mansoorpervaizdev@gmail.com

import asyncio
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date, timedelta

from data_manager.data_reader import DataReader, FieldName
from strategies.momentum import (
    RateOfChangeStrategy,
    MovingAverageCrossoverStrategy,
    RSIStrategy
)
from backtester import BackTester


async def run_single_strategy_example():
    """Run a single strategy backtest example."""
    # Initialize the data reader
    data_reader = DataReader()
    
    # Create a strategy
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
    symbol = 'AAPL'
    start_date = date(2022, 1, 1)
    end_date = date(2022, 12, 31)
    
    # Run the backtest
    print(f"Running RSI strategy backtest for {symbol} from {start_date} to {end_date}...")
    report = await backtester.backtest(
        strategy=rsi_strategy,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date
    )
    
    # Print the results
    print("\nBacktest Results:")
    for key, value in report.summary().items():
        print(f"{key}: {value}")
    
    # Plot the equity curve
    plt.figure(figsize=(12, 6))
    report.plot_equity_curve()
    plt.savefig(f"{symbol}_rsi_strategy.png")
    plt.close()
    
    return report


async def compare_strategies_example():
    """Compare multiple strategies example."""
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
    symbol = 'MSFT'
    start_date = date(2022, 1, 1)
    end_date = date(2022, 12, 31)
    
    # Run the comparison
    print(f"\nComparing strategies for {symbol} from {start_date} to {end_date}...")
    results = await backtester.compare_strategies(
        strategies=[roc_strategy, ma_strategy, rsi_strategy],
        symbol=symbol,
        start_date=start_date,
        end_date=end_date
    )
    
    # Print the results
    print("\nStrategy Comparison:")
    for strategy_name, report in results.items():
        print(f"\n{strategy_name}:")
        print(f"Total Return: {report.total_return:.2f}%")
        print(f"Annualized Return: {report.annualized_return:.2f}%")
        print(f"Sharpe Ratio: {report.sharpe_ratio:.2f}")
        print(f"Max Drawdown: {report.max_drawdown:.2f}%")
        print(f"Number of Trades: {len(report.trades)}")
    
    # Plot the equity curves
    plt.figure(figsize=(12, 6))
    for strategy_name, report in results.items():
        plt.plot(report.equity_curve.index, report.equity_curve, label=strategy_name)
    
    plt.title(f'Strategy Comparison for {symbol}')
    plt.xlabel('Date')
    plt.ylabel('Capital ($)')
    plt.legend()
    plt.grid(True)
    plt.savefig(f"{symbol}_strategy_comparison.png")
    plt.close()
    
    return results


async def compare_to_benchmark_example():
    """Compare a strategy to a benchmark example."""
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
    symbol = 'GOOGL'
    benchmark_symbol = 'SPY'
    start_date = date(2022, 1, 1)
    end_date = date(2022, 12, 31)
    
    # Run the comparison
    print(f"\nComparing MA strategy for {symbol} against {benchmark_symbol} from {start_date} to {end_date}...")
    strategy_report, benchmark_data = await backtester.compare_to_benchmark(
        strategy=ma_strategy,
        symbol=symbol,
        benchmark_symbol=benchmark_symbol,
        start_date=start_date,
        end_date=end_date
    )
    
    # Print the results
    print("\nStrategy vs Benchmark:")
    print(f"Strategy Total Return: {strategy_report.total_return:.2f}%")
    
    # Calculate benchmark return
    benchmark_return = ((benchmark_data.iloc[-1] - benchmark_data.iloc[0]) / benchmark_data.iloc[0]) * 100
    print(f"Benchmark Total Return: {benchmark_return:.2f}%")
    
    # Plot the comparison
    plt.figure(figsize=(12, 6))
    strategy_report.plot_equity_curve(benchmark_data=benchmark_data)
    plt.savefig(f"{symbol}_vs_{benchmark_symbol}.png")
    plt.close()
    
    return strategy_report, benchmark_data


async def main():
    """Run all examples."""
    # Run the single strategy example
    await run_single_strategy_example()
    
    # Run the strategy comparison example
    await compare_strategies_example()
    
    # Run the benchmark comparison example
    await compare_to_benchmark_example()


if __name__ == "__main__":
    asyncio.run(main())