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
import os
from datetime import date, timedelta
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import itertools


from data_manager.data_reader import DataReader, FieldName
from strategies.momentum import (
    RateOfChangeStrategy,
    MovingAverageCrossoverStrategy,
    RSIStrategy
)
from backtester import BackTester


def get_available_tickers():
    """Get a list of all tickers that have data available."""
    data_dir = Path(DataReader.DATA_LOCATION)
    tickers = []

    # Check if the directory exists
    if data_dir.exists() and data_dir.is_dir():
        # Get all .pkl.gz files
        for file in data_dir.glob("*.pkl.gz"):
            # Extract ticker symbol from filename (remove .pkl.gz extension)
            ticker = file.stem.split('.')[0]
            tickers.append(ticker)

    return tickers


async def run_single_strategy_example(input_file=None, strategy_name="MovingAverageCrossover"):
    """
    Run a single strategy backtest example.

    Args:
        input_file (str, optional): Path to a CSV file containing tickers to process.
                                   If not provided, all available tickers will be used.
        strategy_name (str, optional): Name of the strategy to use. 
                                      Options: "MovingAverageCrossover", "RSI", "RateOfChange".
                                      Default is "MovingAverageCrossover".
    """
    # Create output directories if they don't exist
    ticker_plots_dir = Path("output/ticker-plots")
    ticker_plots_dir.mkdir(parents=True, exist_ok=True)

    cumulative_results_dir = Path("output/cumulative-results")
    cumulative_results_dir.mkdir(parents=True, exist_ok=True)

    # Initialize the data reader
    data_reader = DataReader()

    # Create a strategy based on the strategy_name parameter
    if strategy_name == "RSI":
        strategy = RSIStrategy(
            data_reader=data_reader,
            window=14,
            oversold=30,
            overbought=70,
            use_trend_filter=True,
            ma_period=200
        )
    elif strategy_name == "RateOfChange":
        strategy = RateOfChangeStrategy(
            data_reader=data_reader,
            n_days=14,
            threshold_pct=5,
            sell_threshold_pct=-3
        )
    else:  # Default to MovingAverageCrossover
        strategy = MovingAverageCrossoverStrategy(
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
    start_date = date(2014, 1, 1)
    end_date = date(2024, 12, 31)

    # Get tickers based on input file or all available tickers
    if input_file and os.path.exists(input_file):
        # Read tickers from the input file
        tickers_df = pd.read_csv(input_file)
        if 'Symbol' in tickers_df.columns:
            tickers = tickers_df['Symbol'].tolist()
            print(f"Using {len(tickers)} tickers from {input_file}")
        else:
            print(f"Warning: 'Symbol' column not found in {input_file}. Using all available tickers instead.")
            tickers = get_available_tickers()
    else:
        # Get all available tickers
        tickers = get_available_tickers()

    print(f"Running {strategy_name} strategy backtest for {len(tickers)} tickers from {start_date} to {end_date}...")

    # Dictionary to store reports for each ticker
    reports = {}

    # Run the backtest for each ticker
    for symbol in tickers:
        try:
            print(f"Processing {symbol}...")
            report = await backtester.backtest(
                strategy=strategy,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )

            # Store the report
            reports[symbol] = report

            # Print the results
            print(f"\nBacktest Results for {symbol}:")
            for key, value in report.summary().items():
                print(f"{key}: {value}")

            # Plot the equity curve
            plt.figure(figsize=(12, 6))
            report.plot_equity_curve()
            plt.savefig(f"output/ticker-plots/{symbol}_{strategy_name.lower()}_strategy.png")
            plt.close()

        except Exception as e:
            print(f"Error processing {symbol}: {str(e)}")

    print(f"Completed backtesting for {len(reports)} tickers.")

    # Generate cumulative report
    if reports:
        print("\n" + "="*50)
        print("CUMULATIVE REPORT FOR ALL SYMBOLS")
        print("="*50)

        # Create a DataFrame with key metrics for each ticker
        report_data = []
        for symbol, report in reports.items():
            report_data.append({
                'Symbol': symbol,
                'Total Return (%)': report.total_return,
                'Annualized Return (%)': report.annualized_return,
                'Win Rate (%)': report.win_rate,
                'Number of Trades': len(report.trades),
                'Profit Factor': report.profit_factor,
                'Max Drawdown (%)': report.max_drawdown,
                'Sharpe Ratio': report.sharpe_ratio
            })

        # Create DataFrame
        df_report = pd.DataFrame(report_data)

        # Calculate aggregate statistics
        summary_stats = {
            'Mean': df_report.mean(numeric_only=True),
            'Median': df_report.median(numeric_only=True),
            'Min': df_report.min(numeric_only=True),
            'Max': df_report.max(numeric_only=True)
        }

        # Display summary statistics
        print("\nSummary Statistics:")
        summary_df = pd.DataFrame(summary_stats)
        print(summary_df.round(2))

        # Display top 10 performers by total return
        print("\nTop 10 Performers by Total Return:")
        top_performers = df_report.sort_values('Total Return (%)', ascending=False).head(10)
        print(top_performers.round(2))

        # Display bottom 10 performers by total return
        print("\nBottom 10 Performers by Total Return:")
        bottom_performers = df_report.sort_values('Total Return (%)', ascending=True).head(10)
        print(bottom_performers.round(2))

        # Plot distribution of total returns
        plt.figure(figsize=(12, 6))
        plt.hist(df_report['Total Return (%)'], bins=20, alpha=0.7)
        plt.axvline(df_report['Total Return (%)'].mean(), color='r', linestyle='dashed', linewidth=1, label=f'Mean: {df_report["Total Return (%)"].mean():.2f}%')
        plt.axvline(df_report['Total Return (%)'].median(), color='g', linestyle='dashed', linewidth=1, label=f'Median: {df_report["Total Return (%)"].median():.2f}%')
        plt.title('Distribution of Total Returns Across All Symbols')
        plt.xlabel('Total Return (%)')
        plt.ylabel('Frequency')
        plt.legend()
        plt.grid(True)
        plt.savefig("output/cumulative-results/cumulative_returns_distribution.png")
        plt.close()

        # Plot top 10 performers
        plt.figure(figsize=(12, 6))
        top_10 = df_report.sort_values('Total Return (%)', ascending=False).head(10)
        plt.bar(top_10['Symbol'], top_10['Total Return (%)'])
        plt.title('Top 10 Performers by Total Return')
        plt.xlabel('Symbol')
        plt.ylabel('Total Return (%)')
        plt.xticks(rotation=45)
        plt.grid(True, axis='y')
        plt.tight_layout()
        plt.savefig("output/cumulative-results/top_10_performers.png")
        plt.close()

        print("\nCumulative report visualizations saved to:")
        print("- output/cumulative-results/cumulative_returns_distribution.png")
        print("- output/cumulative-results/top_10_performers.png")

        # Save the full report to CSV
        csv_filename = "output/cumulative-results/cumulative_backtest_report.csv"
        df_report.to_csv(csv_filename, index=False)
        print(f"- Full report saved to {csv_filename}")

    return reports


async def compare_strategies_example():
    """Compare multiple strategies example for all available tickers."""
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
    start_date = date(2014, 1, 1)
    end_date = date(2024, 12, 31)

    # Get all available tickers
    tickers = get_available_tickers()
    print(f"\nComparing strategies for {len(tickers)} tickers from {start_date} to {end_date}...")

    # Dictionary to store results for each ticker
    all_results = {}

    # Run the comparison for each ticker
    for symbol in tickers:
        try:
            print(f"Processing {symbol}...")
            results = await backtester.compare_strategies(
                strategies=[roc_strategy, ma_strategy, rsi_strategy],
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )

            # Store the results
            all_results[symbol] = results

            # Print the results
            print(f"\nStrategy Comparison for {symbol}:")
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
            plt.savefig(f"output/ticker-plots/{symbol}_strategy_comparison.png")
            plt.close()

        except Exception as e:
            print(f"Error processing {symbol}: {str(e)}")

    print(f"Completed strategy comparison for {len(all_results)} tickers.")
    return all_results


async def compare_to_benchmark_example():
    """Compare a strategy to a benchmark example for all available tickers."""
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
    start_date = date(2022, 1, 1)
    end_date = date(2022, 12, 31)

    # Get all available tickers
    tickers = get_available_tickers()
    print(f"\nComparing MA strategy for {len(tickers)} tickers against {benchmark_symbol} from {start_date} to {end_date}...")

    # Dictionary to store results for each ticker
    all_results = {}

    # Run the comparison for each ticker
    for symbol in tickers:
        try:
            # Skip the benchmark symbol itself
            if symbol == benchmark_symbol:
                continue

            print(f"Processing {symbol}...")
            strategy_report, benchmark_data = await backtester.compare_to_benchmark(
                strategy=ma_strategy,
                symbol=symbol,
                benchmark_symbol=benchmark_symbol,
                start_date=start_date,
                end_date=end_date
            )

            # Store the results
            all_results[symbol] = (strategy_report, benchmark_data)

            # Print the results
            print(f"\nStrategy vs Benchmark for {symbol}:")
            print(f"Strategy Total Return: {strategy_report.total_return:.2f}%")

            # Calculate benchmark return
            benchmark_return = ((benchmark_data.iloc[-1] - benchmark_data.iloc[0]) / benchmark_data.iloc[0]) * 100
            print(f"Benchmark Total Return: {benchmark_return:.2f}%")

            # Plot the comparison
            plt.figure(figsize=(12, 6))
            strategy_report.plot_equity_curve(benchmark_data=benchmark_data)
            plt.savefig(f"output/ticker-plots/{symbol}_vs_{benchmark_symbol}.png")
            plt.close()

        except Exception as e:
            print(f"Error processing {symbol}: {str(e)}")

    print(f"Completed benchmark comparison for {len(all_results)} tickers.")
    return all_results

def evaluate_rsi_combo(symbol, window, oversold, overbought, ma_period, start_date, end_date):
    try:
        data_reader = DataReader()
        strategy = RSIStrategy(
            data_reader=data_reader,
            window=window,
            oversold=oversold,
            overbought=overbought,
            use_trend_filter=True,
            ma_period=ma_period
        )
        backtester = BackTester(data_reader=data_reader, initial_capital=10000, transaction_cost_pct=0.1)
        report = asyncio.run(backtester.backtest(strategy, symbol, start_date, end_date))

        return {
            "Symbol": symbol,
            "Window": window,
            "Oversold": oversold,
            "Overbought": overbought,
            "MA": ma_period,
            "Sharpe": report.sharpe_ratio,
            "Return": report.total_return,
            "Drawdown": report.max_drawdown,
            "Trades": len(report.trades)
        }
    except Exception as e:
        return {
            "Symbol": symbol,
            "Error": str(e),
            "Window": window,
            "Oversold": oversold,
            "Overbought": overbought,
            "MA": ma_period
        }


def evaluate_wrapper(args):
    return evaluate_rsi_combo(*args)


def run_rsi_optimization():
    start_date = date(2014, 1, 1)
    end_date = date(2024, 12, 31)

    tickers = get_available_tickers()[:100]  # You can remove slicing to run on all

    param_grid = list(itertools.product([5, 10, 14], [25, 30, 35], [65, 70, 75], [100, 150, 200]))
    tasks = [(symbol, w, os, ob, ma, start_date, end_date)
             for symbol in tickers
             for (w, os, ob, ma) in param_grid]

    print(f"Running {len(tasks)} RSI grid tests across {len(tickers)} symbols...")

    with ProcessPoolExecutor() as executor:
        results = list(executor.map(evaluate_wrapper, tasks))

    df = pd.DataFrame(results)
    df.to_csv("output/cumulative-results/rsi_grid_optimization_results.csv", index=False)
    print("Results saved to output/cumulative-results/rsi_grid_optimization_results.csv")
async def main():
    """Run all examples."""
    # Run the single strategy example with S&P 500 tickers
    sp500_file = os.path.join("data", "SP500.csv")
    print(f"\nRunning single strategy example with S&P 500 tickers from {sp500_file}")
    # Uncomment the following lines to run with different strategies or all available tickers

    # this is not a tradable strategy in its current form.
    # Even though MA crossover systems are popular, they:
    # Work better on commodities or FX, not equities.
    # Need trend filters (ADX, slope filters, volume filters).
    # Often benefit from volatility or momentum confirmation.
    #
    # MovingAverageCrossover doesnt work
    # await run_single_strategy_example(input_file=sp500_file, strategy_name="MovingAverageCrossover")
    #
    #
    # RSI doesn't work
    # 1. Only 41 out of 81000 tests were “good”
    # That’s 0.05% success rate — effectively noise.
    # Most configurations had Sharpe < 0, meaning the strategy underperformed risk-free returns.
    #
    # 2. Returns were driven by a few lucky trades
    # Even the best configurations often had fewer than 20 trades in 10 years.
    # This isn't repeatable — it’s statistically flimsy.
    #
    # 3. Highly parameter-sensitive
    # Tiny changes in RSI window or thresholds led to wildly different outcomes.
    # This is a sign of overfitting, not robust alpha.
    #
    # 4. Drawdowns remain high
    # 20–30% drawdowns for modest returns are unattractive for short-term trading.
    # You’d get better risk-adjusted returns just holding SPY.
    #
    # RSI doesnt work
    # await run_single_strategy_example(input_file=sp500_file, strategy_name="RSI")

    # Rate of change doesn't work
    # ❌ Is not profitable or robust across a broad universe.
    # ❌ Has very few consistently winning tickers.
    # ❌ Underperforms passive investing (e.g., SPY buy-and-hold).
    # ⚠️ Shows signs of overfitting + signal noise.

    await run_single_strategy_example(input_file=sp500_file, strategy_name="RateOfChange")
    # await run_single_strategy_example(strategy_name="MovingAverageCrossover")

    # Run the strategy comparison example
    # await compare_strategies_example()

    # Run the benchmark comparison example
    # await compare_to_benchmark_example()


if __name__ == "__main__":
    asyncio.run(main())
