import pandas;
import os


class SymbolManager:
    DATA_LOCATION = os.path.join("..", "data")

    def __init__(self, symbols_file=""):
        if symbols_file is None or symbols_file == "":
            symbols_file = os.path.join("../data/_nasdaq_screener_1714506906799.csv")
            #symbols_file = os.path.join("../data/_500.csv")
            # nasdaq_screener_1714506906799
        self.df = pandas.read_csv(symbols_file)

    # def get_symbols(self, symbol_count=None):
    #     return [x for x in self.df["Symbol"][:symbol_count]]

    def get_symbols_space_separated(self, symbol_count=None):
        symbols = []
        for sym in self.df["Symbol"].values:
            if isinstance(sym, str) and sym.isalnum():
                symbols.append(sym)
        return symbols


if __name__ == "__main__":
    smNasdaq = SymbolManager("../data/_nasdaq_screener_1714506906799.csv")
    nasdaq_symbols = smNasdaq.get_symbols_space_separated()

    sm500 = SymbolManager("../data/_500.csv")
    sm500_symbols = sm500.get_symbols_space_separated()

    print(set(sm500_symbols).issubset(set(nasdaq_symbols)))
