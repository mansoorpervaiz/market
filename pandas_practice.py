from pandas import Series, DataFrame
import pandas as pd

obj = Series([4, 7, -5, 3])

obj2 = Series([4, 7, -5, 3], index=['d', 'b', 'a', 'c'])
# print(obj2)
# print(obj2[['a','d']])

sdata = {'Ohio': 35000, 'Texas': 71000, 'Oregon': 16000, 'Utah': 5000}
obj3 = Series(sdata)



states = ['California',  'Oregon', 'Texas', 'Ohio']
obj4 = Series(sdata, index=states)
# print(pd.isnull(obj4))
#
# print(pd.notnull(obj4))
#
# print(obj3+obj4)
#
# obj4.index.name = "states"
# obj4.name = "population"
# print(obj4)


import pandas_datareader.data as web
import datetime

import pandas_datareader.nasdaq_trader as nasdaq
start = datetime.datetime(2020,1,1)
end = datetime.datetime(2020,4,17)

# google = web.DataReader("GOOGL", "yahoo", start, end)
# print(google.head())


syms = nasdaq.get_nasdaq_symbols()

print(type(syms))

count = 0
print("****************************************")
print("****************************************")
print("****************************************")
for index, row in syms.iterrows():
    count += 1
    if count > 500:
        break
    print(index)
    print('____________________________')


