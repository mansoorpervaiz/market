# Copyright (c) 2025 Mansoor Pervaiz
# All rights reserved.
#
# This file is part of a proprietary software project.
# Unauthorized copying, distribution, modification, or use of this file,
# via any medium, is strictly prohibited unless explicit permission is granted
# by the author.
#
# For licensing inquiries, contact: mansoorpervaizdev@gmail.com

import pandas as pd
import numpy as np
from enum import Enum

class Signal(Enum):
    BUY = 1
    SELL = -1
    HOLD = 0

class MomentumStrategy:
    """Base class for momentum trading strategies."""
    
    def __init__(self, data_reader):
        """
        Initialize the strategy with a data reader.
        
        Args:
            data_reader: An instance of DataReader to access financial data.
        """
        self.data_reader = data_reader
    
    async def generate_signals(self, symbol, start_date, end_date):
        """
        Generate trading signals for the given symbol and date range.
        
        Args:
            symbol (str): The stock symbol.
            start_date: The start date for the analysis.
            end_date: The end date for the analysis.
            
        Returns:
            pd.DataFrame: DataFrame with dates as index and signals as values.
        """
        raise NotImplementedError("Subclasses must implement this method")


class RateOfChangeStrategy(MomentumStrategy):
    """
    Rate of Change (ROC) strategy.
    Buy when the price has increased more than X% over the past N days.
    """
    
    def __init__(self, data_reader, n_days=14, threshold_pct=5, sell_threshold_pct=-3):
        """
        Initialize the ROC strategy.
        
        Args:
            data_reader: An instance of DataReader.
            n_days (int): Number of days to calculate ROC over.
            threshold_pct (float): Percentage threshold for buy signals.
            sell_threshold_pct (float): Percentage threshold for sell signals.
        """
        super().__init__(data_reader)
        self.n_days = n_days
        self.threshold_pct = threshold_pct
        self.sell_threshold_pct = sell_threshold_pct
    
    async def generate_signals(self, symbol, start_date, end_date):
        """Generate buy/sell signals based on Rate of Change."""
        # Get data for a longer period to calculate ROC
        from datetime import timedelta
        extended_start_date = start_date - timedelta(days=self.n_days * 2)
        
        # Get price data
        df = await self.data_reader.get_data(symbol, extended_start_date, end_date)
        
        # Calculate Rate of Change
        df['roc'] = df['close'].pct_change(self.n_days) * 100
        
        # Generate signals
        df['signal'] = Signal.HOLD.value
        df.loc[df['roc'] >= self.threshold_pct, 'signal'] = Signal.BUY.value
        df.loc[df['roc'] <= self.sell_threshold_pct, 'signal'] = Signal.SELL.value
        
        # Filter to the requested date range
        result = df.loc[df.index >= start_date, ['signal']]
        return result


class MovingAverageCrossoverStrategy(MomentumStrategy):
    """
    Moving Average Crossover strategy.
    Buy when a short-term moving average crosses above a long-term moving average.
    """
    
    def __init__(self, data_reader, short_window=20, long_window=50):
        """
        Initialize the Moving Average Crossover strategy.
        
        Args:
            data_reader: An instance of DataReader.
            short_window (int): Window for the short-term moving average.
            long_window (int): Window for the long-term moving average.
        """
        super().__init__(data_reader)
        self.short_window = short_window
        self.long_window = long_window
    
    async def generate_signals(self, symbol, start_date, end_date):
        """Generate buy/sell signals based on Moving Average Crossover."""
        # Get data for a longer period to calculate moving averages
        from datetime import timedelta
        extended_start_date = start_date - timedelta(days=self.long_window * 2)
        
        # Get price data
        df = await self.data_reader.get_data(symbol, extended_start_date, end_date)
        
        # Calculate moving averages
        df['short_ma'] = df['close'].rolling(window=self.short_window).mean()
        df['long_ma'] = df['close'].rolling(window=self.long_window).mean()
        
        # Generate signals
        df['signal'] = Signal.HOLD.value
        
        # Buy when short MA crosses above long MA
        df.loc[(df['short_ma'] > df['long_ma']) & 
               (df['short_ma'].shift(1) <= df['long_ma'].shift(1)), 
               'signal'] = Signal.BUY.value
        
        # Sell when short MA crosses below long MA
        df.loc[(df['short_ma'] < df['long_ma']) & 
               (df['short_ma'].shift(1) >= df['long_ma'].shift(1)), 
               'signal'] = Signal.SELL.value
        
        # Filter to the requested date range
        result = df.loc[df.index >= start_date, ['signal']]
        return result


class RSIStrategy(MomentumStrategy):
    """
    Relative Strength Index (RSI) strategy.
    Buy when RSI crosses above 30 (oversold), sell when it crosses below 70 (overbought).
    """
    
    def __init__(self, data_reader, window=14, oversold=30, overbought=70):
        """
        Initialize the RSI strategy.
        
        Args:
            data_reader: An instance of DataReader.
            window (int): Window for RSI calculation.
            oversold (int): Threshold for oversold condition.
            overbought (int): Threshold for overbought condition.
        """
        super().__init__(data_reader)
        self.window = window
        self.oversold = oversold
        self.overbought = overbought
    
    async def generate_signals(self, symbol, start_date, end_date):
        """Generate buy/sell signals based on RSI."""
        # Get data for a longer period to calculate RSI
        from datetime import timedelta
        extended_start_date = start_date - timedelta(days=self.window * 3)
        
        # Get price data
        df = await self.data_reader.get_data(symbol, extended_start_date, end_date)
        
        # Calculate RSI
        df['price_change'] = df['close'].diff()
        df['gain'] = df['price_change'].clip(lower=0)
        df['loss'] = -df['price_change'].clip(upper=0)
        
        # Calculate average gain and loss
        df['avg_gain'] = df['gain'].rolling(window=self.window).mean()
        df['avg_loss'] = df['loss'].rolling(window=self.window).mean()
        
        # Calculate RS and RSI
        df['rs'] = df['avg_gain'] / df['avg_loss']
        df['rsi'] = 100 - (100 / (1 + df['rs']))
        
        # Generate signals
        df['signal'] = Signal.HOLD.value
        
        # Buy when RSI crosses above oversold threshold
        df.loc[(df['rsi'] > self.oversold) & 
               (df['rsi'].shift(1) <= self.oversold), 
               'signal'] = Signal.BUY.value
        
        # Sell when RSI crosses below overbought threshold
        df.loc[(df['rsi'] < self.overbought) & 
               (df['rsi'].shift(1) >= self.overbought), 
               'signal'] = Signal.SELL.value
        
        # Filter to the requested date range
        result = df.loc[df.index >= start_date, ['signal']]
        return result