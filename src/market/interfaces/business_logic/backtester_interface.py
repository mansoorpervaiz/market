# Copyright (c) 2025 Mansoor Pervaiz
# All rights reserved.
#
# This file is part of a proprietary software project.
# Unauthorized copying, distribution, modification, or use of this file,
# via any medium, is strictly prohibited unless explicit permission is granted
# by the author.
#
# For licensing inquiries, contact: mansoorpervaizdev@gmail.com

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Dict, Any

from market.interfaces.data_access.data_reader_interface import DataReaderInterface
from market.interfaces.business_logic.strategy_interface import StrategyInterface


class BacktestReportInterface(ABC):
    """
    Interface for backtest reports.

    This interface defines the contract that all backtest reports must adhere to,
    providing metrics and visualizations for strategy performance.
    """

    @abstractmethod
    def total_return(self) -> float:
        """
        Calculate the total return of the strategy.

        Returns:
            The total return as a percentage.
        """
        pass

    @abstractmethod
    def annualized_return(self) -> float:
        """
        Calculate the annualized return of the strategy.

        Returns:
            The annualized return as a percentage.
        """
        pass

    @abstractmethod
    def win_rate(self) -> float:
        """
        Calculate the win rate of the strategy.

        Returns:
            The win rate as a percentage.
        """
        pass

    @abstractmethod
    def max_drawdown(self) -> float:
        """
        Calculate the maximum drawdown of the strategy.

        Returns:
            The maximum drawdown as a percentage.
        """
        pass

    @abstractmethod
    def plot_equity_curve(self, benchmark_data=None) -> None:
        """
        Plot the equity curve of the strategy.

        Args:
            benchmark_data: Optional benchmark data to compare against.
        """
        pass

    @abstractmethod
    def summary(self) -> Dict[str, Any]:
        """
        Generate a summary of the backtest results.

        Returns:
            Dictionary containing key metrics.
        """
        pass


class BackTesterInterface(ABC):
    """
    Interface for backtesting trading strategies.

    This interface defines the contract that all backtesters must adhere to,
    allowing for different implementations (e.g., event-driven, vectorized).
    """

    @abstractmethod
    def __init__(self, data_reader: DataReaderInterface, initial_capital: float = 10000, transaction_cost_pct: float = 0.1):
        """
        Initialize the backtester.

        Args:
            data_reader: An instance of a class implementing DataReaderInterface.
            initial_capital: The initial capital for the backtest.
            transaction_cost_pct: The transaction cost as a percentage.
        """
        pass

    @abstractmethod
    def backtest(self, strategy: StrategyInterface, symbol: str, start_date: date, end_date: date) -> BacktestReportInterface:
        """
        Backtest a strategy on a symbol within a date range.

        Args:
            strategy: An instance of a class implementing StrategyInterface.
            symbol: The stock symbol.
            start_date: The start date for the backtest.
            end_date: The end date for the backtest.

        Returns:
            An instance of a class implementing BacktestReportInterface.
        """
        pass

    @abstractmethod
    def compare_strategies(self, strategies: List[StrategyInterface], symbol: str, start_date: date, end_date: date) -> Dict[str, BacktestReportInterface]:
        """
        Compare multiple strategies on a symbol within a date range.

        Args:
            strategies: List of instances of classes implementing StrategyInterface.
            symbol: The stock symbol.
            start_date: The start date for the backtest.
            end_date: The end date for the backtest.

        Returns:
            Dictionary mapping strategy names to backtest reports.
        """
        pass

    @abstractmethod
    def compare_to_benchmark(self, strategy: StrategyInterface, symbol: str, benchmark_symbol: str, start_date: date, end_date: date) -> Dict[str, BacktestReportInterface]:
        """
        Compare a strategy to a benchmark within a date range.

        Args:
            strategy: An instance of a class implementing StrategyInterface.
            symbol: The stock symbol.
            benchmark_symbol: The benchmark symbol.
            start_date: The start date for the backtest.
            end_date: The end date for the backtest.

        Returns:
            Dictionary mapping strategy and benchmark names to backtest reports.
        """
        pass
