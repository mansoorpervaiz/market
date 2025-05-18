    def _process_data_chunk(self, data, capital, position, trades, current_trade, symbol):
        """
        Process a chunk of data for backtesting.
        
        Args:
            data (pd.DataFrame): Chunk of data to process.
            capital (float): Current capital.
            position (int): Current position (shares).
            trades (list): List of completed trades.
            current_trade (Trade or None): Current open trade if any.
            symbol (str): Symbol being processed.
            
        Returns:
            tuple: Updated capital, position, trades, current_trade, equity_curve.
        """
        equity_curve = {}
        
        for idx, row in data.iterrows():
            date = idx
            price = row['close']
            signal = row['signal']
            
            # Calculate equity for this date (cash + value of any position)
            equity = capital + (position * price)
            equity_curve[date] = equity
            
            # Process based on signal
            if signal == Signal.BUY.value and position == 0:
                # Calculate shares to buy (use all available capital minus transaction cost)
                transaction_cost = capital * (self.transaction_cost_pct / 100)
                available_capital = capital - transaction_cost
                shares_to_buy = int(available_capital / price)
                
                if shares_to_buy > 0:
                    # Update capital and position
                    cost = (shares_to_buy * price) + transaction_cost
                    capital -= cost
                    position = shares_to_buy
                    
                    # Create a new trade
                    current_trade = Trade(
                        symbol=symbol,
                        entry_date=date,
                        entry_price=price,
                        shares=shares_to_buy
                    )
                    
            elif signal == Signal.SELL.value and position > 0 and current_trade is not None:
                # Calculate sale proceeds and transaction cost
                sale_value = position * price
                transaction_cost = sale_value * (self.transaction_cost_pct / 100)
                net_proceeds = sale_value - transaction_cost
                
                # Update capital and position
                capital += net_proceeds
                position = 0
                
                # Complete the trade
                current_trade.exit_date = date
                current_trade.exit_price = price
                trades.append(current_trade)
                current_trade = None
                
        return capital, position, trades, current_trade, equity_curve
