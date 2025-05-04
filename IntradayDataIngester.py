import asyncio
import json
import os
import pandas as pd
import aiohttp
import ssl
from datetime import datetime, timedelta
import calendar

from data_manager.alpha_vantage import AsyncAlphaVantageDownloader
from data_manager.symbol_manager import SymbolManager

def generate_month_list(start_year=2014, start_month=1):
    """
    Generate a list of months from start_year/start_month to the current month
    in YYYY-MM format required by Alpha Vantage API.
    """
    current_date = datetime.now()
    months = []

    for year in range(start_year, current_date.year + 1):
        # Determine the range of months for this year
        start_m = start_month if year == start_year else 1
        end_m = current_date.month if year == current_date.year else 12

        for month in range(start_m, end_m + 1):
            months.append(f"{year}-{month:02d}")

    # Return in reverse order (most recent first) to get the most recent data first
    return list(reversed(months))

async def process_symbol(symbol: str,
                         downloader: AsyncAlphaVantageDownloader,
                         not_found: list,
                         sem: asyncio.Semaphore,
                         interval: str = "60min"):
    # Create directory for this interval if it doesn't exist
    os.makedirs(f"./data/intraday/json/{interval}", exist_ok=True)
    os.makedirs(f"./data/intraday/pickle/{interval}", exist_ok=True)

    # Generate list of months from Jan 2014 to current month
    months = generate_month_list(2014, 1)
    print(f"Processing {symbol} for {len(months)} months from {months[-1]} to {months[0]}")

    # Dictionary to store combined time series data
    combined_time_series = {}
    time_series_key = f"Time Series ({interval})"

    # Metadata from the most recent request
    latest_metadata = {}

    # Flag to track if we got any data for this symbol
    got_data = False

    # Variables to track consecutive empty months
    consecutive_empty_months = 0
    max_consecutive_empty = 3  # Stop after 3 consecutive months with no data

    for month in months:
        # If we've had too many consecutive empty months, skip the rest
        # This helps avoid unnecessary API calls for symbols that weren't listed in earlier years
        if consecutive_empty_months >= max_consecutive_empty:
            print(f"Skipping remaining months for {symbol} after {max_consecutive_empty} consecutive empty months")
            break

        # acquire against the loop's own semaphore for each month
        async with sem:
            try:
                # For intraday data, we need to specify the interval and month
                data = await downloader.download(
                    symbol, 
                    function="TIME_SERIES_INTRADAY", 
                    interval=interval,
                    month=month,
                    outputsize="full"
                )

                # Check if we got valid data for this month
                ts = data.get(time_series_key)
                if ts:
                    # Update metadata with the most recent response
                    if not latest_metadata and "Meta Data" in data:
                        latest_metadata = data["Meta Data"]

                    # Merge this month's data into the combined dictionary
                    combined_time_series.update(ts)
                    got_data = True
                    consecutive_empty_months = 0  # Reset counter when we get data
                    print(f"Got data for {symbol} for month {month} with {len(ts)} data points")
                else:
                    consecutive_empty_months += 1
                    print(f"No data for {symbol} for month {month} (consecutive empty: {consecutive_empty_months})")
            except Exception as e:
                consecutive_empty_months += 1
                print(f"Error processing {symbol} for month {month}: {str(e)}")

    # If we got data for any month, save it
    if got_data:
        # Create a complete data structure with metadata and time series
        complete_data = {
            "Meta Data": latest_metadata,
            time_series_key: combined_time_series
        }

        # write JSON
        with open(f"./data/intraday/json/{interval}/{symbol}.json", "w") as f:
            json.dump(complete_data, f)

        # Save to pickle
        df = pd.DataFrame.from_dict(combined_time_series, orient="index")
        df.to_pickle(f"./data/intraday/pickle/{interval}/{symbol}.pkl.gz", compression="gzip")

        print(f"Saved combined data for {symbol} with {len(combined_time_series)} total data points")
    else:
        not_found.append(symbol)
        print(f"No data found for {symbol} across all months")


async def main():
    # ensure base data folders exist
    os.makedirs("./data/intraday", exist_ok=True)
    os.makedirs("./data/intraday/json", exist_ok=True)
    os.makedirs("./data/intraday/pickle", exist_ok=True)

    # Define the intervals we want to download
    intervals = ["1min"] #, "5min", "15min", "30min", "60min"]

    not_found = []
    # Reduce concurrency to 5 since we're making many more API calls per symbol
    sem = asyncio.Semaphore(5)

    # Calculate and display the number of months we'll be processing
    months = generate_month_list(2014, 1)
    print(f"Will process data for {len(months)} months from {months[-1]} to {months[0]}")

    # Optional: Process only a subset of symbols to avoid hitting API limits
    # Set max_symbols to None to process all symbols
    max_symbols = 200  # Process 10 symbols at a time

    # Optional: Start from a specific symbol (useful for resuming after a previous run)
    start_from_symbol = None  # Set to a symbol name to start from that symbol

    # Check if we should resume from a previous run
    resume = True  # Set to False to start from the beginning regardless of previous runs

    # Dictionary to store missing symbols for each interval
    missing_symbols_by_interval = {}

    # Check for missing symbols files for each interval
    for interval in intervals:
        missing_symbols_path = f"./data/intraday/missing_symbols_{interval}.txt"
        if os.path.exists(missing_symbols_path):
            print(f"Found missing symbols file for {interval} at {missing_symbols_path}")
            with open(missing_symbols_path, "r") as f:
                missing_symbols = [line.strip() for line in f if line.strip()]
            missing_symbols_by_interval[interval] = missing_symbols
            print(f"Read {len(missing_symbols)} missing symbols for {interval}")

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
        print("Fetching Russell 1000 symbols from Wikipedia...")
        sm.load_russell_1000_symbols()

        all_symbols = sm.get_symbols_space_separated()
        print(f"Fetched {len(all_symbols)} symbols from Russell 1000 Index")

        # Save symbols to a text file in the data folder
        symbols_file = sm.save_symbols_to_file("symbols.txt")
        print(f"Symbols saved to {symbols_file}")

        # Process each symbol for each interval
        for interval in intervals:
            print(f"Processing {interval} interval data...")
            interval_not_found = []

            # If resume is enabled and no specific start symbol is provided,
            # try to read the last processed symbol from file
            if resume and not start_from_symbol:
                last_symbol_file = f"./data/intraday/last_processed_symbol_{interval}.txt"
                if os.path.exists(last_symbol_file):
                    with open(last_symbol_file, "r") as f:
                        last_symbol = f.read().strip()
                        if last_symbol:
                            # Find the index of the last symbol and start from the next one
                            try:
                                last_index = all_symbols.index(last_symbol)
                                if last_index < len(all_symbols) - 1:  # If not the last symbol
                                    start_from_symbol = all_symbols[last_index + 1]
                                    print(f"Resuming from symbol {start_from_symbol} (after {last_symbol})")
                                else:
                                    print(f"Already processed all symbols for {interval}")
                                    continue  # Skip this interval
                            except ValueError:
                                print(f"Last symbol {last_symbol} not found in current symbol list, starting from beginning")

            # Filter symbols based on start_from_symbol if specified
            if start_from_symbol:
                try:
                    start_index = all_symbols.index(start_from_symbol)
                    filtered_symbols = all_symbols[start_index:]
                    print(f"Starting from symbol {start_from_symbol} (index {start_index})")
                except ValueError:
                    print(f"Symbol {start_from_symbol} not found, starting from the beginning")
                    filtered_symbols = all_symbols
            else:
                filtered_symbols = all_symbols

            # Limit the number of symbols if max_symbols is specified
            if max_symbols is not None:
                filtered_symbols = filtered_symbols[:max_symbols]
                print(f"Processing a batch of {len(filtered_symbols)} symbols")

            # Show progress information
            if start_from_symbol and filtered_symbols:
                try:
                    total_symbols = len(all_symbols)
                    current_index = all_symbols.index(filtered_symbols[0])
                    remaining = total_symbols - current_index
                    progress_pct = (current_index / total_symbols) * 100
                    print(f"Progress: {current_index}/{total_symbols} symbols processed ({progress_pct:.2f}%), {remaining} symbols remaining")
                except ValueError:
                    print("Could not calculate progress information")

            # Process each symbol from API
            api_tasks = [
                process_symbol(sym, downloader, interval_not_found, sem, interval)
                for sym in filtered_symbols
            ]

            # Process missing symbols for this interval if any
            missing_symbols = missing_symbols_by_interval.get(interval, [])
            if missing_symbols:
                # Filter and limit missing symbols as well
                if start_from_symbol:
                    try:
                        start_index = missing_symbols.index(start_from_symbol)
                        filtered_missing = missing_symbols[start_index:]
                    except ValueError:
                        filtered_missing = missing_symbols
                else:
                    filtered_missing = missing_symbols

                if max_symbols is not None:
                    # Only include missing symbols if we have room in our batch
                    remaining_slots = max_symbols - len(filtered_symbols)
                    if remaining_slots > 0:
                        filtered_missing = filtered_missing[:remaining_slots]
                    else:
                        filtered_missing = []

                if filtered_missing:
                    print(f"Processing {len(filtered_missing)} missing symbols for {interval}...")
                    missing_tasks = [
                        process_symbol(sym, downloader, interval_not_found, sem, interval)
                        for sym in filtered_missing
                    ]
                    # Combine all tasks
                    tasks = api_tasks + missing_tasks
                else:
                    tasks = api_tasks
            else:
                tasks = api_tasks

            # Execute all tasks
            await asyncio.gather(*tasks)

            # If we're processing in batches, write the last processed symbol to a file
            # so we can resume from there in the next run
            if max_symbols is not None and filtered_symbols:
                last_symbol = filtered_symbols[-1]
                with open(f"./data/intraday/last_processed_symbol_{interval}.txt", "w") as f:
                    f.write(last_symbol)
                print(f"Last processed symbol: {last_symbol}, saved to ./data/intraday/last_processed_symbol_{interval}.txt")

            # Reset start_from_symbol for the next interval
            # This is important because we want to resume from the correct symbol for each interval
            start_from_symbol = None

            # write missing symbols for this interval
            with open(f"./data/intraday/missing_symbols_{interval}.txt", "w") as f:
                for sym in interval_not_found:
                    f.write(sym + "\n")

            not_found.extend(interval_not_found)
            print(f"Missing symbols for {interval} written to ./data/intraday/missing_symbols_{interval}.txt")

    print("Intraday data ingestion complete.")


if __name__ == "__main__":
    asyncio.run(main())
