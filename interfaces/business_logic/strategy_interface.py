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
import pandas as pd
from typing import Any

from interfaces.data_access.data_reader_interface import DataReaderInterface


class StrategyInterface(ABC):
    """
    Interface for trading strategies.
    
    This interface defines the contract that all trading strategies must adhere to,
    allowing for different implementations (e.g., momentum, breakout, mean reversion).
    """
    
    @abstractmethod
    def __init__(self, data_reader: DataReaderInterface):
        """
        Initialize the strategy with a data reader.
        
        Args:
            data_reader: An instance of a class implementing DataReaderInterface.
        """
        pass
    
    @abstractmethod
    async def generate_signals(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        """
        Generate buy/sell signals for a symbol within a date range.
        
        Args:
            symbol: The stock symbol.
            start_date: The start date for the analysis.
            end_date: The end date for the analysis.
            
        Returns:
            DataFrame with dates as index and signals as values.
        """
        pass