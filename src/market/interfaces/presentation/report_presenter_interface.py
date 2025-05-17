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
from typing import Dict, Any, Optional

from market.interfaces.business_logic.backtester_interface import BacktestReportInterface


class ReportPresenterInterface(ABC):
    """
    Interface for presenting backtest reports.

    This interface defines the contract that all report presenters must adhere to,
    allowing for different presentation formats (e.g., console, HTML, PDF).
    """

    @abstractmethod
    def present_summary(self, report: BacktestReportInterface) -> None:
        """
        Present a summary of the backtest report.

        Args:
            report: An instance of a class implementing BacktestReportInterface.
        """
        pass

    @abstractmethod
    def present_equity_curve(self, report: BacktestReportInterface, benchmark_report: Optional[BacktestReportInterface] = None) -> None:
        """
        Present the equity curve of the backtest report.

        Args:
            report: An instance of a class implementing BacktestReportInterface.
            benchmark_report: Optional benchmark report to compare against.
        """
        pass

    @abstractmethod
    def present_trade_list(self, report: BacktestReportInterface) -> None:
        """
        Present the list of trades from the backtest report.

        Args:
            report: An instance of a class implementing BacktestReportInterface.
        """
        pass

    @abstractmethod
    def present_comparison(self, reports: Dict[str, BacktestReportInterface]) -> None:
        """
        Present a comparison of multiple backtest reports.

        Args:
            reports: Dictionary mapping strategy names to backtest reports.
        """
        pass

    @abstractmethod
    def export_report(self, report: BacktestReportInterface, file_path: str) -> None:
        """
        Export the backtest report to a file.

        Args:
            report: An instance of a class implementing BacktestReportInterface.
            file_path: Path to the file where the report will be saved.
        """
        pass
