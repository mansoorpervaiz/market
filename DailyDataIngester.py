import asyncio
import json
import os
import pandas as pd
import aiohttp
import ssl

from data_manager.alpha_vantage import AsyncAlphaVantageDownloader
from data_manager.symbol_manager import SymbolManager

async def process_symbol(symbol: str,
                         downloader: AsyncAlphaVantageDownloader,
                         not_found: list,
                         sem: asyncio.Semaphore):
    # acquire against the loop's own semaphore
    async with sem:
        data = await downloader.download(symbol)

    # write JSON
    with open(f"./data/daily/json/{symbol}.json", "w") as f:
        json.dump(data, f)

    # pickle if present
    ts = data.get("Time Series (Daily)")
    if ts:
        df = pd.DataFrame.from_dict(ts, orient="index")
        df.to_pickle(f"./data/daily/pickle/{symbol}.pkl.gz", compression="gzip")
    else:
        not_found.append(symbol)


async def main():
    # ensure base data folders exist
    os.makedirs("./data/daily", exist_ok=True)
    os.makedirs("./data/daily/json", exist_ok=True)
    os.makedirs("./data/daily/pickle", exist_ok=True)

    not_found = []
    sem = asyncio.Semaphore(5)

    # Check if missing_symbols.txt exists and read symbols from it
    missing_symbols_path = "./data/daily/missing_symbols.txt"
    missing_symbols = []
    if os.path.exists(missing_symbols_path):
        print(f"Found missing symbols file at {missing_symbols_path}")
        with open(missing_symbols_path, "r") as f:
            missing_symbols = [line.strip() for line in f if line.strip()]
        print(f"Read {len(missing_symbols)} missing symbols")

    # Create a custom SSL context that doesn't verify certificates
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        downloader = AsyncAlphaVantageDownloader(session)

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

        # Process each symbol from API
        api_tasks = [
            process_symbol(sym, downloader, not_found, sem)
            for sym in all_symbols
        ]

        # Process missing symbols if any
        if missing_symbols:
            print(f"Processing {len(missing_symbols)} missing symbols...")
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
    with open("./data/daily/missing_symbols.txt", "w") as f:
        for sym in not_found:
            f.write(sym + "\n")

    print("Missing symbols written to ./data/daily/missing_symbols.txt")



if __name__ == "__main__":
    asyncio.run(main())
