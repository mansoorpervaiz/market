import asyncio
import json
import os
import pandas as pd
import aiohttp

from data_manager.alpha_vantage import AsyncAlphaVantageDownloader
from data_manager.symbol_manager import SymbolManager

async def process_symbol(symbol: str,
                         downloader: AsyncAlphaVantageDownloader,
                         not_found: list,
                         sem: asyncio.Semaphore):
    # acquire against the loop’s own semaphore
    async with sem:
        data = await downloader.download(symbol)

    # write JSON
    with open(f"./data/json/{symbol}.json", "w") as f:
        json.dump(data, f)

    # pickle if present
    ts = data.get("Time Series (Daily)")
    if ts:
        df = pd.DataFrame.from_dict(ts, orient="index")
        df.to_pickle(f"./data/pickle/{symbol}.pkl.gz", compression="gzip")
    else:
        not_found.append(symbol)


async def main():
    # ensure base data folders exist
    os.makedirs("./data/json", exist_ok=True)
    os.makedirs("./data/pickle", exist_ok=True)

    sm = SymbolManager("./data/_nasdaq_screener_1714506906799.csv")
    all_symbols = sm.get_symbols_space_separated()
    not_found = []

    sem = asyncio.Semaphore(500)
    async with aiohttp.ClientSession() as session:
        downloader = AsyncAlphaVantageDownloader(session)
        tasks = [
            process_symbol(sym, downloader, not_found, sem)
            for sym in all_symbols
        ]
        await asyncio.gather(*tasks)

    # write missing symbols
    with open("./data/missing_symbols.txt", "w") as f:
        for sym in not_found:
            f.write(sym + "\n")

    print("Missing symbols written to ./data/missing_symbols.txt")



if __name__ == "__main__":
    asyncio.run(main())
