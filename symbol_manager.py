import pandas;
import os
class SymbolMananger:
    def __init__(self, symbols_file=""):
        if symbols_file is None or symbols_file == "":
            symbols_file = os.path.join(".", "data", "nasdaq_screener_1607213376036.csv")
            
        self.df = pandas.read_csv(symbols_file)
        print("")

    def get_symbols(self, symbol_count=None):
        return [x for x in self.df["Symbol"][:symbol_count]]

    def get_symbols_space_separated(self, symbol_count=None):
        from functools import reduce
        return reduce((lambda x, y: x + " " + y),
                         self.get_symbols(symbol_count))


