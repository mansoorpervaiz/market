# Copyright (c) 2025 Mansoor Pervaiz
# All rights reserved.
#
# This file is part of a proprietary software project.
# Unauthorized copying, distribution, modification, or use of this file,
# via any medium, is strictly prohibited unless explicit permission is granted
# by the author.
#
# For licensing inquiries, contact: mansoorpervaizdev@gmail.com

import os
import asyncio
import json
from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd
from enum import Enum

from data_manager.alpha_vantage import AsyncAlphaVantageDownloader
from logger import get_logger

# Initialize logger
logger = get_logger(__name__)


class DataReader:
    DATA_PICKLE_LOCATION = os.path.join("data", "daily", "pickle")
    DATA_JSON_LOCATION = os.path.join("data", "daily", "json")

    def __init__(self):
        self.avDownloader = AsyncAlphaVantageDownloader()
        self.loaded_data = None
        self.loaded_data_symbol = None

        # Ensure data directories exist
        os.makedirs(self.DATA_PICKLE_LOCATION, exist_ok=True)
        os.makedirs(self.DATA_JSON_LOCATION, exist_ok=True)

    def _load_data(self, symbol):
        try:
            df = pd.read_pickle(os.path.join(self.DATA_PICKLE_LOCATION, symbol + ".pkl.gz"))
            logger.debug(f"Loaded data columns: {df.columns.tolist()}")

            # Rename columns to match what the code expects
            if '4. close' in df.columns and 'close' not in df.columns:
                df.rename(
                    columns={
                        '1. open': FieldName.OPEN.value,
                        '2. high': FieldName.HIGH.value,
                        '3. low': FieldName.LOW.value,
                        '4. close': FieldName.CLOSE.value,
                        '5. adjusted close': FieldName.ADJUSTED_CLOSE.value,
                        '6. volume': FieldName.VOLUME.value
                    },
                    inplace=True)

                # Convert string values to numeric
                for col in [FieldName.OPEN.value, FieldName.HIGH.value, FieldName.LOW.value, 
                           FieldName.CLOSE.value, FieldName.ADJUSTED_CLOSE.value]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')

                # Convert volume to int if it exists
                if FieldName.VOLUME.value in df.columns:
                    df[FieldName.VOLUME.value] = pd.to_numeric(df[FieldName.VOLUME.value], errors='coerce').astype('Int64')

            return df
        except FileNotFoundError:
            logger.warning(f"File {symbol} not found")
            return None

    def _save_data(self, symbol, symbol_data):
        """
        Save the DataFrame to pickle format

        :param symbol: Stock symbol
        :param symbol_data: DataFrame containing stock data
        """
        symbol_data.to_pickle(os.path.join(self.DATA_PICKLE_LOCATION, symbol + ".pkl.gz"))

    async def _download_and_save_data(self, symbol):
        symbol_data_dict = await self.avDownloader.download(symbol)

        # Save the original JSON response
        if symbol_data_dict:
            # Ensure the JSON directory exists
            os.makedirs(self.DATA_JSON_LOCATION, exist_ok=True)

            # Save the JSON data
            json_path = os.path.join(self.DATA_JSON_LOCATION, f"{symbol}.json")
            with open(json_path, "w") as f:
                json.dump(symbol_data_dict, f)
            logger.info(f"Saved JSON data for {symbol}")

        # Convert to DataFrame
        dataframe = self._convert_dict_to_dataframe(symbol_data_dict)

        # Only save if we have valid data
        if not dataframe.empty:
            self._save_data(symbol=symbol, symbol_data=dataframe)
            logger.info(f"Saved pickle data for {symbol}")
        else:
            logger.error(f"Error processing {symbol}: 'Time Series (Daily)'")

        return dataframe

    async def _update_with_latest_data(self, symbol, last_date_in_df, previous_data):
        symbol_data_dict = await self.avDownloader.download(symbol)

        # Save the original JSON response
        if symbol_data_dict:
            # Ensure the JSON directory exists
            os.makedirs(self.DATA_JSON_LOCATION, exist_ok=True)

            # Save the JSON data
            json_path = os.path.join(self.DATA_JSON_LOCATION, f"{symbol}.json")
            with open(json_path, "w") as f:
                json.dump(symbol_data_dict, f)
            logger.info(f"Updated JSON data for {symbol}")

        recent_data = self._convert_dict_to_dataframe(symbol_data_dict)

        # If we couldn't get valid data, return the previous data
        if recent_data.empty:
            logger.error(f"Error processing {symbol}: 'Time Series (Daily)'")
            return previous_data

        # Ensure both dataframes have datetime.date indices
        if not all(isinstance(idx, date) for idx in previous_data.index):
            previous_data.index = pd.to_datetime(previous_data.index).date

        if not all(isinstance(idx, date) for idx in recent_data.index):
            recent_data.index = pd.to_datetime(recent_data.index).date

        mask = (recent_data.index > last_date_in_df)
        df_with_new_data = recent_data.loc[mask]

        # Only update if we have new data
        if not df_with_new_data.empty:
            updated_data = pd.concat([previous_data, df_with_new_data]).drop_duplicates().sort_index()
            self._save_data(symbol=symbol, symbol_data=updated_data)
            logger.info(f"Updated pickle data for {symbol}")
            return updated_data
        else:
            return previous_data

    def _convert_dict_to_dataframe(self, symbol_data):
        # Check if the response contains the expected data
        if not symbol_data or "Time Series (Daily)" not in symbol_data:
            logger.error(f"Error processing symbol: 'Time Series (Daily)' not found in response")
            # Return an empty DataFrame with the expected columns
            return pd.DataFrame(columns=[
                FieldName.OPEN.value,
                FieldName.HIGH.value,
                FieldName.LOW.value,
                FieldName.CLOSE.value,
                FieldName.ADJUSTED_CLOSE.value,
                FieldName.VOLUME.value
            ])

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

        if 'volume' in dataframe.columns:
            dataframe['volume'] = dataframe['volume'].astype(int)
        dataframe.index = pd.to_datetime(dataframe.index).date
        return dataframe

    def _convert_dict_to_dataframe_simple(self, symbol_data):
        # Check if the response contains the expected data
        if not symbol_data or "Time Series (Daily)" not in symbol_data:
            logger.error(f"Error processing symbol: 'Time Series (Daily)' not found in response")
            # Return an empty DataFrame with the expected columns
            return pd.DataFrame(columns=[
                FieldName.OPEN.value,
                FieldName.HIGH.value,
                FieldName.LOW.value,
                FieldName.CLOSE.value,
                FieldName.VOLUME.value
            ])

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

        if 'volume' in dataframe.columns:
            dataframe['volume'] = dataframe['volume'].astype(int)
        dataframe.index = pd.to_datetime(dataframe.index).date
        return dataframe

    async def get_data(self, symbol, start_date, end_date):
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
        # Check if we need to load data (different symbol or data not loaded yet)
        if self.loaded_data_symbol != symbol or self.loaded_data is None:

            dataframe = self._load_data(symbol)
            # did not find data on local disk, downloading and saving it
            if dataframe is None:
                logger.info(f"Data for {symbol} not found locally. Downloading from Alpha Vantage...")
                dataframe = await self._download_and_save_data(symbol=symbol)
                logger.info(f"Downloaded and saved data for {symbol}")

            # is the data up-to-date
            if dataframe.empty:
                # If dataframe is empty, we need to skip the date comparison
                logger.warning(f"Empty dataframe for {symbol}, skipping date comparison")
                last_date_in_df = None
            else:
                last_date_in_df = dataframe.index.max()
                logger.debug(f"last_date_in_df type: {type(last_date_in_df)}, value: {last_date_in_df}")
                logger.debug(f"end_date type: {type(end_date)}, value: {end_date}")

                # Convert to datetime.date if needed
                if isinstance(last_date_in_df, str):
                    last_date_in_df = pd.to_datetime(last_date_in_df).date()

            # Only try to update if we have a valid last_date_in_df and it's before end_date
            if last_date_in_df is not None and last_date_in_df < end_date:
                dataframe = await self._update_with_latest_data(symbol=symbol,
                                                          last_date_in_df=last_date_in_df,
                                                          previous_data=dataframe)
            self.loaded_data_symbol = symbol
            self.loaded_data = dataframe

            # Ensure index is datetime.date for comparison
            if not all(isinstance(idx, date) for idx in self.loaded_data.index):
                self.loaded_data.index = pd.to_datetime(self.loaded_data.index).date

        mask = (self.loaded_data.index >= start_date) & (self.loaded_data.index <= end_date)
        result = self.loaded_data.loc[mask]
        print(f"DataFrame columns before return: {result.columns.tolist()}")
        return result

    async def get_mean(self, symbol, start_date, end_date, field_name):
        field = FieldName(field_name)
        df = await self.get_data(symbol, start_date, end_date)

        return df[field.value].mean()

    async def get_sma(self, symbol, current_date, number_of_days, field_name):
        field = FieldName(field_name)
        start_date = current_date - timedelta(days=number_of_days)
        df = await self.get_data(symbol, start_date, current_date)
        return df[field.value].mean()

    async def get_value(self, symbol, for_date, for_field):
        d = await self.get_data(symbol=symbol, start_date=for_date, end_date=for_date)
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
    async def main():
        reader = DataReader()
        # data = reader._load_data("MSFT")
        # data = await reader.get_data(symbol="MSFT", start_date="2024-03-01", end_date="2024-04-01")
        # print(data)
        # data = await reader.get_data(symbol="MSFT", start_date="2024-03-01", end_date="2024-04-01")
        # data = await reader.get_mean("MSFT", "2024-03-01", "2024-04-01", FieldName.OPEN.value)

        # data = await reader.get_data(symbol="MSFT", start_date=date(2024, 3, 1), end_date=date(2024, 4, 1))
        # print(data)
        # data = await reader.get_data(symbol="MSFT", start_date=date(2024, 3, 1), end_date=date(2024, 3, 1))
        data = await reader.get_value(symbol="MSFT", for_date=date(2024, 4, 29), for_field=FieldName.CLOSE)

        logger.debug(f"Data type: {type(data)}")
        logger.debug(f"Data value: {data}")

    asyncio.run(main())
