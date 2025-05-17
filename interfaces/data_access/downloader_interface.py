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
from typing import Dict, Any, List, Optional


class DownloaderInterface(ABC):
    """
    Interface for downloaders that fetch financial data from external sources.
    
    This interface defines the contract that all downloaders must adhere to,
    allowing for different implementations (e.g., Alpha Vantage, Yahoo Finance).
    """
    
    @abstractmethod
    async def download(self, symbol: str, function: str = "TIME_SERIES_DAILY_ADJUSTED", **kwargs) -> Dict[str, Any]:
        """
        Download financial data for a symbol.
        
        Args:
            symbol: The stock symbol.
            function: The API function to call.
            **kwargs: Additional parameters for the API call.
            
        Returns:
            Dictionary containing the downloaded data.
        """
        pass
    
    @abstractmethod
    async def get_symbols(self, exchange: Optional[str] = None) -> List[str]:
        """
        Get a list of stock symbols from the data source.
        
        Args:
            exchange: Optional exchange to filter symbols by.
            
        Returns:
            List of stock symbols.
        """
        pass