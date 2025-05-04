# Copyright (c) 2025 Mansoor Pervaiz
# All rights reserved.
#
# This file is part of a proprietary software project.
# Unauthorized copying, distribution, modification, or use of this file,
# via any medium, is strictly prohibited unless explicit permission is granted
# by the author.
#
# For licensing inquiries, contact: mansoorpervaizdev@gmail.com

import statistics
import traceback
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta

from data_manager.symbol_manager import SymbolManager
from portfolio.buy_prediction import ShortAverageGood, BuyAtSMA200, RecommendationType
from logger import get_logger

# Initialize logger
logger = get_logger(__name__)


class BackTester:
    def __init__(self):
        pass

    def _process_sale(self, sell_price, sell_date, bought_price, bought_date, report):
        transaction_profit = sell_price - bought_price
        transaction_profit_percent = transaction_profit / float(bought_price) * 100
        if transaction_profit_percent > 0:
            report.wins.append(transaction_profit_percent)
            report.win_days.append(sell_date - bought_date)
        elif transaction_profit_percent < 0:
            report.losses.append(transaction_profit_percent)
            report.loss_days.append(sell_date - bought_date)

    def backtest(self, algorithm, symbol, start_date, end_date):
        algo1 = algorithm()
        report = BackTestReport()

        bought_price = None
        bought_date = None
        sell_price_limit = None

        current_date = start_date
        current_prediction = None
        while current_date < end_date:
            try:
                current_prediction = algo1.predict(symbol=symbol, dt=current_date, bought_price=bought_price)
            except Exception as e:
                logger.error(f"Error predicting for {symbol} on {current_date}: {str(e)}")
                logger.debug(traceback.format_exc())
                return report
            if current_prediction.recommendation_type == RecommendationType.SELL:
                self._process_sale(current_prediction.price, current_date, bought_price, bought_date, report)
                bought_price = None
                sell_price_limit = None
            elif current_prediction.recommendation_type == RecommendationType.BUY:
                bought_price = current_prediction.price
                bought_date = current_date
                sell_price_limit = current_prediction.price
            else:
                if sell_price_limit and current_prediction.price and current_prediction.price > sell_price_limit:
                    sell_price_limit = current_prediction.price

            current_date += relativedelta(days=1)

        if bought_price is not None:
            logger.debug(f"Final state - Price: {current_prediction.price}, Date: {current_date}, Bought Price: {bought_price}, Bought Date: {bought_date}")
            logger.debug(f"Final recommendation: {current_prediction.recommendation_type}")

            self._process_sale(current_prediction.price, current_date, bought_price, bought_date, report)

        # report.generate_report()
        return report


class BackTestReport:
    def __init__(self):
        self.wins = []
        self.losses = []
        self.win_days = []
        self.loss_days = []

    def generate_report(self):
        total_wins_and_losses = self.wins + self.losses
        logger.info("BackTestReport")
        logger.info(f"Average percentage: {statistics.mean(total_wins_and_losses)}")
        logger.info(f"Number of wins: {len(self.wins)}")
        logger.info(f"Number of losses: {len(self.losses)}")
        logger.debug(f"Wins: {self.wins}")
        logger.debug(f"Losses: {self.losses}")

    def extend(self, report):
        self.wins.extend(report.wins)
        self.losses.extend(report.losses)
        self.win_days.extend(report.win_days)
        self.loss_days.extend(report.loss_days)


from multiprocessing import Pool

if __name__ == '__main__':
    start_time = datetime.now()

    back_tester = BackTester()
    end_date = date.today()

    total_report = BackTestReport()

    sm = SymbolManager(symbols_file="./data/_nasdaq_screener_1714506906799.csv")
    all_symbols = sm.get_symbols_space_separated()

    start_date = end_date - relativedelta(years=3)
    start_id = None
    rate = 0
    # for i, symbol in enumerate(all_symbols):
    #     if start_id and i < start_id:
    #         continue
    #     loop_start = datetime.now()
    #     print(f"{i+1}/{len(all_symbols)}. {symbol}, running at rate: {rate}")
    #     symbol_report = back_tester.backtest(ShortAverageGood, symbol, start_date, end_date)
    #     total_report.extend(symbol_report)
    #
    #     diff = datetime.now() - loop_start
    #     rate = float(60) / diff.total_seconds()
    pooled = []
    pool_size = 10
    pooled = 0
    args_for_starmap = []

    for i, symbol in enumerate(all_symbols):
        if start_id and i < start_id:
            continue

        loop_start = datetime.now()

        logger.info(f"{i+1}/{len(all_symbols)}: Queueing symbol {symbol}")
        args_for_starmap.append((BuyAtSMA200, symbol, start_date, end_date))
        pooled += 1
        if pooled < pool_size:
            continue
        with Pool(pooled) as p:
            reports = p.starmap(back_tester.backtest, args_for_starmap)
            for report in reports:
                total_report.extend(report)

        pooled = 0
        args_for_starmap = []

        diff = datetime.now() - loop_start
        rate = pool_size * float(60) / diff.total_seconds()
        logger.info(f"Current processing rate: {rate:.2f} symbols per minute")
        # loop_start = datetime.now()
        # print(f"{i + 1}/{len(all_symbols)}. {symbol}, running at rate: {rate}")
        # symbol_report = back_tester.backtest(ShortAverageGood, symbol, start_date, end_date)
        # total_report.extend(symbol_report)

        # diff = datetime.now() - loop_start
        # rate = float(60) / diff.total_seconds()

    total_report.generate_report()
    logger.info(f"Total execution time: {datetime.now() - start_time}")
