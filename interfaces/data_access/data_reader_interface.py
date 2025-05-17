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
from typing import Dict, Any, Optional
import pandas as pd


class DataReaderInterface(ABC):
    """
    Interface for data readers that provide financial data.
    
    This interface defines the contract that all data readers must adhere to,
    allowing for different implementations (e.g., from local files, APIs, databases).
    """
    
    @abstractmethod
    def get_data(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        """
        Get financial data for a symbol within a date range.
        
        Args:
            symbol: The stock symbol.
            start_date: The start date for the data.
            end_date: The end date for the data.
            
        Returns:
            DataFrame with financial data (open, high, low, close, volume, etc.).
        """
        pass
    
    @abstractmethod
    def get_mean(self, symbol: str, start_date: date, end_date: date, field_name: str) -> float:
        """
        Get the mean value of a field for a symbol within a date range.
        
        Args:
            symbol: The stock symbol.
            start_date: The start date for the data.
            end_date: The end date for the data.
            field_name: The field to calculate the mean for (e.g., 'close', 'volume').
            
        Returns:
            The mean value of the field.
        """
        pass
    
    @abstractmethod
    def get_sma(self, symbol: str, current_date: date, number_of_days: int, field_name: str) -> float:
        """
        Get the simple moving average for a field.
        
        Args:
            symbol: The stock symbol.
            current_date: The date to calculate the SMA for.
            number_of_days: The number of days to include in the SMA.
            field_name: The field to calculate the SMA for (e.g., 'close', 'volume').
            
        Returns:
            The simple moving average value.
        """
        pass
    
    @abstractmethod
    def get_value(self, symbol: str, for_date: date, for_field: str) -> float:
        """
        Get the value of a field for a symbol on a specific date.
        
        Args:
            symbol: The stock symbol.
            for_date: The date to get the value for.
            for_field: The field to get the value for (e.g., 'close', 'volume').
            
        Returns:
            The value of the field on the specified date.
        """
        pass