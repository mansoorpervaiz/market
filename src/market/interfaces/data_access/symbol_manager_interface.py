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
from typing import List, Optional


class SymbolManagerInterface(ABC):
    """
    Interface for symbol managers that provide stock symbols.
    
    This interface defines the contract that all symbol managers must adhere to,
    allowing for different implementations (e.g., from files, APIs, databases).
    """
    
    @abstractmethod
    def get_symbols_space_separated(self, symbol_count: Optional[int] = None) -> List[str]:
        """
        Get a list of stock symbols.
        
        Args:
            symbol_count: Optional limit on the number of symbols to return.
            
        Returns:
            List of stock symbols.
        """
        pass
    
    @abstractmethod
    def load_russell_1000_symbols(self) -> List[str]:
        """
        Load symbols for Russell 1000 constituents.
        
        Returns:
            List of Russell 1000 stock symbols.
        """
        pass
    
    @abstractmethod
    async def load_symbols_from_api(self, exchanges: Optional[List[str]] = None) -> None:
        """
        Load symbols from an API.
        
        Args:
            exchanges: List of exchanges to fetch symbols for.
                      If None, fetches symbols from all exchanges.
        """
        pass
    
    @abstractmethod
    def save_symbols_to_file(self, file_path: str = "symbols.txt") -> str:
        """
        Save the symbols to a text file.
        
        Args:
            file_path: Path to the file where symbols will be saved.
            
        Returns:
            The path to the saved file.
        """
        pass