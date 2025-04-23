import pandas
import os
import asyncio
from .alpha_vantage import AsyncAlphaVantageDownloader


class SymbolManager:
    DATA_LOCATION = os.path.join("..", "data")

    def __init__(self, symbols_file="", downloader=None):
        """
        Initialize the SymbolManager.

        Args:
            symbols_file: Optional path to a CSV file containing symbols.
                         If provided, symbols will be loaded from this file.
                         If not provided, symbols will be fetched from Alpha Vantage API.
            downloader: Optional AsyncAlphaVantageDownloader instance.
                       Required if symbols_file is not provided.
        """
        self.symbols = []
        self.downloader = downloader

        # If a file is provided, load symbols from it
        if symbols_file and symbols_file != "":
            self.df = pandas.read_csv(symbols_file)
            self._load_symbols_from_dataframe()

    def _load_symbols_from_dataframe(self):
        """Load symbols from the dataframe."""
        self.symbols = []
        for sym in self.df["Symbol"].values:
            if isinstance(sym, str) and sym.isalnum():
                self.symbols.append(sym)

    async def load_symbols_from_api(self, exchanges=None):
        """
        Load symbols from Alpha Vantage API.

        Args:
            exchanges: List of exchanges to fetch symbols for (e.g., ['NYSE', 'NASDAQ']).
                      If None, fetches symbols from all exchanges.
        """
        if self.downloader is None:
            raise ValueError("Downloader is required to fetch symbols from API")

        self.symbols = []

        if exchanges is None:
            # Fetch symbols from all exchanges
            self.symbols = await self.downloader.get_symbols()
        else:
            # Fetch symbols for each specified exchange
            for exchange in exchanges:
                exchange_symbols = await self.downloader.get_symbols(exchange)
                self.symbols.extend(exchange_symbols)

            # Remove duplicates
            self.symbols = list(set(self.symbols))

    def get_symbols_space_separated(self, symbol_count=None):
        """
        Get the list of symbols.

        Args:
            symbol_count: Optional limit on the number of symbols to return.

        Returns:
            List of symbols.
        """
        if symbol_count is not None:
            return self.symbols[:symbol_count]
        return self.symbols

    def save_symbols_to_file(self, file_path="symbols.txt"):
        """
        Save the symbols to a text file.

        Args:
            file_path: Path to the file where symbols will be saved.
                      If not an absolute path, it will be relative to DATA_LOCATION.
        """
        # If file_path is not an absolute path, make it relative to DATA_LOCATION
        if not os.path.isabs(file_path):
            # Check if we're in the project root or in a subdirectory
            if os.path.exists("./data"):
                file_path = os.path.join("./data", file_path)
            else:
                file_path = os.path.join(self.DATA_LOCATION, file_path)

        # Ensure the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Write symbols to file
        with open(file_path, "w") as f:
            for symbol in self.symbols:
                f.write(symbol + "\n")

        return file_path
