import pandas as pd
import json

from data_manager.alpha_vantage import AlphaVantageDownloader
from data_manager.symbol_manager import SymbolManager

if __name__ == "__main__":
    sm = SymbolManager("./data/_nasdaq_screener_1714506906799.csv")
    all_symbols = sm.get_symbols_space_separated()
    avDownloader = AlphaVantageDownloader()
    symbols_not_found = []
    for symbol in all_symbols:
        data = avDownloader.download(symbol)
        with open(f"./data/json/{symbol}.json", "w") as file:
            json.dump(data, file)
        try:
            dataframe = pd.DataFrame.from_dict(data["Time Series (Daily)"], orient='index')
            dataframe.to_pickle(f"./data/pickle/{symbol}.pkl.gz", compression='gzip')
        except KeyError:
            symbols_not_found.append(symbol)
    print(symbols_not_found)



