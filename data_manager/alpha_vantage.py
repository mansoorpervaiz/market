import requests
from time import sleep
# replace the "demo" apikey below with your own key from https://www.alphavantage.co/support/#api-key
# url = 'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=IBM&outputsize=compact&apikey=ADKYDT7BSK2IL5O1'
# r = requests.get(url)
# data_manager = r.json()
#
# print(data_manager)

ALPHA_VANTAGE_DATE_FORMAT = '%Y-%m-%d'

KEYS = [
    "VBY4QJJEI73XVQT3",
    "ADKYDT7BSK2IL5O1",
    "C09R44C5Y37M2C8W" # premium key
]

class AlphaVantageDownloader:
    def __init__(self, api_key="C09R44C5Y37M2C8W"):
        self.api_key = api_key

    def download(self, symbol, all_historical_data=True):
        output_size = "full" if all_historical_data else "compact"
        # url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&outputsize={output_size}&apikey={self.api_key}'
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol={symbol}&outputsize={output_size}&apikey={self.api_key}'
        print(url)
        retries_allowed = 20
        data = None
        while retries_allowed > 0:
            r = requests.get(url)
            data = r.json()
            if 'Meta Data' in data:
                return data
            #sleep(1)
            retries_allowed -= 1
        return data


if __name__ == "__main__":
    a = AlphaVantageDownloader()
    data = a.download("AAMC")
    print(len(data['Time Series (Daily)']))
    count = 1
