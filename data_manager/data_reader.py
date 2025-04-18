import os
from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd
from enum import Enum

from data_manager.alpha_vantage import AlphaVantageDownloader


class DataReader:
    DATA_LOCATION = os.path.join("..", "data")

    def __init__(self):
        self.avDownloader = AlphaVantageDownloader()
        self.loaded_data = None
        self.loaded_data_symbol = None

    def _load_data(self, symbol):
        try:
            return pd.read_pickle(os.path.join(self.DATA_LOCATION, symbol + ".pkl"))
        except FileNotFoundError:
            print(f"File {symbol} not found")
            return None

    def _save_data(self, symbol, symbol_data):
        symbol_data.to_pickle(os.path.join(self.DATA_LOCATION, symbol + ".pkl"))

    def _download_and_save_data(self, symbol, all_historical_data=False):
        symbol_data_dict = self.avDownloader.download(symbol, all_historical_data=all_historical_data)
        dataframe = self._convert_dict_to_dataframe(symbol_data_dict)
        self._save_data(symbol=symbol,
                        symbol_data=dataframe)
        return dataframe

    def _update_with_latest_data(self, symbol, last_date_in_df, previous_data):
        symbol_data_dict = self.avDownloader.download(symbol, all_historical_data=False)
        recent_data = self._convert_dict_to_dataframe(symbol_data_dict)
        mask = (recent_data.index > last_date_in_df)
        df_with_new_data = recent_data.loc[mask]
        updated_data = pd.concat([previous_data, df_with_new_data]).drop_duplicates().sort_index()
        self._save_data(symbol=symbol,
                        symbol_data=updated_data)
        return updated_data

    def _convert_dict_to_dataframe(self, symbol_data):
        # dataframe = pd.DataFrame.from_dict(data_manager["Time Series (Daily)"], orient='index')
        dataframe = pd.DataFrame.from_dict(symbol_data["Time Series (Daily)"], dtype=float, orient='index')
        dataframe.rename(
            columns={
                '1. open': FieldName.OPEN.value,
                '2. high': FieldName.HIGH.value,
                '3. low': FieldName.LOW.value,
                '4. close': FieldName.CLOSE.value,
                '5. adjusted close': FieldName.ADJUSTED_CLOSE.value,
                '6. volume': FieldName.VOLUME.value
            },
            inplace=True)

        dataframe['volume'] = dataframe['volume'].astype(int)
        dataframe.index = pd.to_datetime(dataframe.index).date
        return dataframe

    def _convert_dict_to_dataframe_simple(self, symbol_data):
        # dataframe = pd.DataFrame.from_dict(data_manager["Time Series (Daily)"], orient='index')
        dataframe = pd.DataFrame.from_dict(symbol_data["Time Series (Daily)"], dtype=float, orient='index')
        dataframe.rename(
            columns={
                '1. open': FieldName.OPEN.value,
                '2. high': FieldName.HIGH.value,
                '3. low': FieldName.LOW.value,
                '4. close': FieldName.CLOSE.value,
                '5. volume': FieldName.VOLUME.value
            },
            inplace=True)

        dataframe['volume'] = dataframe['volume'].astype(int)
        dataframe.index = pd.to_datetime(dataframe.index).date
        return dataframe

    def get_data(self, symbol, start_date, end_date):
        """
        If data_manager file in local storage missing:
            download full data_manager
        else
            load data_manager
        if not end date in memory download compact data_manager and merge
        if start date or end date not in data_manager return error
        else return data_manager

        :param symbol: string for stock symbol
        :param start_date: string for start date in format YYYY-MM-DD
        :param end_date: string for end date in format YYYY-MM-DD
        :return: pandas dataframe
        """
        if self.loaded_data_symbol != symbol:

            dataframe = self._load_data(symbol)
            # did not find data on local disk, downloading and saving it
            if dataframe is None:
                dataframe = self._download_and_save_data(symbol=symbol, all_historical_data=True)

            # is the data up-to-date
            last_date_in_df = dataframe.index.max()
            if last_date_in_df < end_date:
                dataframe = self._update_with_latest_data(symbol=symbol,
                                                          last_date_in_df=last_date_in_df,
                                                          previous_data=dataframe)
            self.loaded_data_symbol = symbol
            self.loaded_data = dataframe

        mask = (self.loaded_data.index >= start_date) & (self.loaded_data.index <= end_date)
        return self.loaded_data.loc[mask]

    def get_mean(self, symbol, start_date, end_date, field_name):
        field = FieldName(field_name)
        df = self.get_data(symbol, start_date, end_date)

        return df[field.value].mean()

    def get_sma(self, symbol, current_date, number_of_days, field_name):
        field = FieldName(field_name)
        start_date = current_date - timedelta(days=number_of_days)
        df = self.get_data(symbol, start_date, current_date)
        return df[field.value].mean()

    def get_value(self, symbol, for_date, for_field):
        d = self.get_data(symbol=symbol, start_date=for_date, end_date=for_date)
        if d.size == 0:
            return None
        return d[for_field.value][0]


class FieldName(Enum):
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    ADJUSTED_CLOSE = "adjusted_close"
    VOLUME = "volume"


if __name__ == '__main__':
    reader = DataReader()
    # data = reader._load_data("MSFT")
    # data = reader.get_data(symbol="MSFT", start_date="2024-03-01", end_date="2024-04-01")
    # print(data)
    # data = reader.get_data(symbol="MSFT", start_date="2024-03-01", end_date="2024-04-01")
    # data = reader.get_mean("MSFT", "2024-03-01", "2024-04-01", FieldName.OPEN.value)

    # data = reader.get_data(symbol="MSFT", start_date=date(2024, 3, 1), end_date=date(2024, 4, 1))
    # print(data)
    # data = reader.get_data(symbol="MSFT", start_date=date(2024, 3, 1), end_date=date(2024, 3, 1))
    data = reader.get_value(symbol="MSFT", for_date=date(2024, 4, 29), for_field=FieldName.CLOSE)

    print(type(data))
    print(data)
