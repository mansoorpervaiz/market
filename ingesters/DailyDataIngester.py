# Copyright (c) 2025 Mansoor Pervaiz
# All rights reserved.
#
# This file is part of a proprietary software project.
# Unauthorized copying, distribution, modification, or use of this file,
# via any medium, is strictly prohibited unless explicit permission is granted
# by the author.
#
# For licensing inquiries, contact: mansoorpervaizdev@gmail.com

"""
Daily Data Ingester

This module is responsible for downloading and storing daily stock data for Russell 1000 constituents.
It uses the Alpha Vantage API to fetch daily stock data and stores it in both JSON and pickle formats.

The module uses the configuration system to determine where to store the data:
- JSON files are stored in the directory specified by config.DATA_JSON_LOCATION
- Pickle files are stored in the directory specified by config.DATA_PICKLE_LOCATION
- Missing symbols are tracked in a file within the daily directory

Usage:
    python ingesters/DailyDataIngester.py

This will:
1. Create necessary directories if they don't exist
2. Fetch Russell 1000 symbols from Wikipedia
3. Download daily data for each symbol
4. Save the data in both JSON and pickle formats
5. Track any symbols for which data could not be retrieved
"""

import asyncio
import json
import os
import pandas as pd
import aiohttp
import ssl
from pathlib import Path

from data_manager.alpha_vantage import AsyncAlphaVantageDownloader
from data_manager.symbol_manager import SymbolManager
from logger import get_logger
from config import config

# Initialize logger
logger = get_logger(__name__)

async def process_symbol(symbol: str,
                         downloader: AsyncAlphaVantageDownloader,
                         not_found: list,
                         sem: asyncio.Semaphore):
    # acquire against the loop's own semaphore
    async with sem:
        data = await downloader.download(symbol)

    # write JSON
    json_path = os.path.join(config.DATA_JSON_LOCATION, f"{symbol}.json")
    with open(json_path, "w") as f:
        json.dump(data, f)

    # pickle if present
    ts = data.get("Time Series (Daily)")
    if ts:
        df = pd.DataFrame.from_dict(ts, orient="index")
        pickle_path = os.path.join(config.DATA_PICKLE_LOCATION, f"{symbol}.pkl.gz")
        df.to_pickle(pickle_path, compression="gzip")
    else:
        not_found.append(symbol)




async def main():
    # ensure base data folders exist
    data_root = Path(config.DATA_ROOT_DIR)
    daily_dir = data_root / "daily"

    # Create directories using configuration values
    os.makedirs(daily_dir, exist_ok=True)
    os.makedirs(config.DATA_JSON_LOCATION, exist_ok=True)
    os.makedirs(config.DATA_PICKLE_LOCATION, exist_ok=True)

    not_found = []
    sem = asyncio.Semaphore(5)

    # Check if missing_symbols.txt exists and read symbols from it
    missing_symbols_path = os.path.join(daily_dir, "missing_symbols.txt")
    missing_symbols = []
    if os.path.exists(missing_symbols_path):
        logger.info(f"Found missing symbols file at {missing_symbols_path}")
        with open(missing_symbols_path, "r") as f:
            missing_symbols = [line.strip() for line in f if line.strip()]
        logger.info(f"Read {len(missing_symbols)} missing symbols")

    # Create a custom SSL context that doesn't verify certificates
    # Note: Disabling SSL verification is not recommended for production use
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        # Pass verify_ssl=False to match the SSL context configuration
        downloader = AsyncAlphaVantageDownloader(session, verify_ssl=False)

        # Initialize SymbolManager with the downloader
        sm = SymbolManager(downloader=downloader)

        # Load symbols for Russell 1000 constituents from Wikipedia
        logger.info("Fetching Russell 1000 symbols from Wikipedia...")
        try:
            sm.load_russell_1000_symbols()
        except Exception as e:
            logger.error(f"Error loading Russell 1000 symbols: {str(e)}")
            # Continue with empty symbols list if loading fails
            pass

        all_symbols = sm.get_symbols_space_separated()
        logger.info(f"Fetched {len(all_symbols)} symbols from Russell 1000 Index")

        # Save symbols to a text file in the data folder
        symbols_file = sm.save_symbols_to_file("symbols.txt")
        logger.info(f"Symbols saved to {symbols_file}")

        # Process each symbol from API
        api_tasks = [
            process_symbol(sym, downloader, not_found, sem)
            for sym in all_symbols
        ]

        # Process missing symbols if any
        if missing_symbols:
            logger.info(f"Processing {len(missing_symbols)} missing symbols...")
            missing_tasks = [
                process_symbol(sym, downloader, not_found, sem)
                for sym in missing_symbols
            ]
            # Combine all tasks
            tasks = api_tasks + missing_tasks
        else:
            tasks = api_tasks

        await asyncio.gather(*tasks)

    # write missing symbols
    with open(missing_symbols_path, "w") as f:
        for sym in not_found:
            f.write(sym + "\n")

    logger.info(f"Missing symbols written to {missing_symbols_path}")



if __name__ == "__main__":
    asyncio.run(main())
