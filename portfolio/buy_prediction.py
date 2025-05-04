from datetime import datetime, timedelta, date
from enum import Enum
from data_manager.data_reader import DataReader, FieldName
from data_manager.alpha_vantage import ALPHA_VANTAGE_DATE_FORMAT
from logger import get_logger

# Initialize logger
logger = get_logger(__name__)


class ShortAverageGood:
    """
    BackTestReport
    Average percentage: 12.961466833093635 (for three years so one year is 4 percent
    number of wins: 472
    number of losses: 783
    """
    def __init__(self):
        self.reader = DataReader()

    # def epoch_to_previous_day(self, epoch_time):
    #     # return epoch_time - datetime.timedelta(days=1)
    #     return datetime.fromtimestamp(epoch_time).strftime(ALPHA_VANTAGE_DATE_FORMAT)

    def predict(self, symbol, dt, bought_price):
        current_price = self.reader.get_value(symbol=symbol, for_date=dt, for_field=FieldName.ADJUSTED_CLOSE)
        initial_prediction = PortfolioRecommendation(symbol=symbol,
                                                     recommendation_type=RecommendationType.NOOP,
                                                     for_date=dt,
                                                     price=current_price)
        if not current_price:
            return initial_prediction

        if bought_price and self.should_sell(symbol, dt, bought_price):
            initial_prediction.recommendation_type = RecommendationType.SELL
        elif not bought_price and self.should_buy(symbol, dt):
            initial_prediction.recommendation_type = RecommendationType.BUY
        return initial_prediction

    def should_buy(self, symbol, dt):
        last_week_time_period = (dt - timedelta(days=7), dt)
        last_month_time_period = (dt - timedelta(days=37), dt - timedelta(days=7))

        last_week_mean = self.reader.get_mean(symbol, last_week_time_period[0],
                                              last_week_time_period[1], FieldName.ADJUSTED_CLOSE.value)
        current_close = self.reader.get_value(symbol=symbol, for_date=dt, for_field=FieldName.ADJUSTED_CLOSE)
        last_month_mean = self.reader.get_mean(symbol, last_month_time_period[0],
                                               last_month_time_period[1], FieldName.ADJUSTED_CLOSE.value)
        # return last_week_mean >= last_month_mean
        # print(f"should buy: current close: {current_close}, last week: {last_week_mean}, should_buy: {current_close >= last_week_mean}")
        return current_close >= last_week_mean

    def should_sell(self, symbol, dt, bought_price):
        current_close = self.reader.get_value(symbol=symbol, for_date=dt, for_field=FieldName.ADJUSTED_CLOSE)
        # print(f"should sell: current close: {current_close}, bought_price: {bought_price}, should_sell: {current_close <= bought_price * 0.85}")

        return current_close <= bought_price * 0.85  # 15% drop in value


class BuyAtSMA200:
    def __init__(self):
        self.reader = DataReader()

    def predict(self, symbol, dt, bought_price):
        current_price = self.reader.get_value(symbol=symbol, for_date=dt, for_field=FieldName.ADJUSTED_CLOSE)
        print(current_price)
        initial_prediction = PortfolioRecommendation(symbol=symbol,
                                                     recommendation_type=RecommendationType.NOOP,
                                                     for_date=dt,
                                                     price=current_price)
        if not current_price:
            return initial_prediction

        if bought_price and self.should_sell(symbol, dt, bought_price):
            initial_prediction.recommendation_type = RecommendationType.SELL
        elif not bought_price and self.should_buy(symbol, dt):
            initial_prediction.recommendation_type = RecommendationType.BUY
        return initial_prediction

    def should_buy(self, symbol, dt):
        period_mean = self.reader.get_sma(symbol=symbol,
                                          current_date=dt,
                                          number_of_days=200,
                                          field_name=FieldName.ADJUSTED_CLOSE.value)


        current_close = self.reader.get_value(symbol=symbol, for_date=dt, for_field=FieldName.ADJUSTED_CLOSE)

        current_start = current_close - (current_close - 0.05)
        return current_start <= period_mean <= current_close

    def should_sell(self, symbol, dt, bought_price):
        current_close = self.reader.get_value(symbol=symbol, for_date=dt, for_field=FieldName.ADJUSTED_CLOSE)
        # print(f"should sell: current close: {current_close}, bought_price: {bought_price}, should_sell: {current_close <= bought_price * 0.85}")

        return current_close <= bought_price * 0.85  # 15% drop in value

class RecommendationType(Enum):
    BUY = 1
    SELL = 2
    NOOP = 3


class PortfolioRecommendation:
    def __init__(self, symbol, recommendation_type, for_date, price):
        self.symbol = symbol
        self.recommendation_type = recommendation_type
        self.for_date = for_date
        self.price = price


if __name__ == '__main__':
    algo1 = ShortAverageGood()
    print(algo1.predict("MSFT", date.today()))
    # x = datetime.now()
    # print(x)
    # print(x.timestamp())
    #
    # epoch = x.timestamp()
    # from_epoch = datetime.fromtimestamp(epoch).strftime(ALPHA_VANTAGE_DATE_FORMAT)
    # print(from_epoch)
