import yfinance as yf

# msft = yf.Ticker("Visa")
# print(msft.info)
# #history = msft.history(period="max")
# temp = yf.Tickers
# history = msft.history(period="3d")
# print(history.size)
# print(len(history))
# #print(history.columns)
#
# print(history)

# for ind in history.index:
#     for col in history.columns:
#         print(col, ind)
#         print(history[col][ind])
#     print("----------------------")
from symbol_manager import SymbolMananger
# msft = yf.Ticker("MSFT")
# history = msft.history(period="3d")
sm = SymbolMananger()
hundred_symbols = sm.get_symbols_space_separated()
data = yf.download(hundred_symbols, period="5d")
print(data.size)
print(len(data))