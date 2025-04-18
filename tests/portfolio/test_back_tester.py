import unittest
import mock
import datetime

from dateutil.relativedelta import relativedelta

from portfolio.back_tester import BackTester
from portfolio.buy_prediction import ShortAverageGood, RecommendationType, PortfolioRecommendation


class TestBackTester(unittest.TestCase):

    @mock.patch('portfolio.buy_prediction.ShortAverageGood.predict')
    def test_one_buy_n_sell_with_win(self, mock_short_average_predict):
        algo_return_values = [
            PortfolioRecommendation("s", RecommendationType.BUY, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.SELL, None, 20),
        ]

        mock_short_average_predict.side_effect = algo_return_values

        back_tester = BackTester()
        end_date = datetime.date.today()
        start_date = end_date - relativedelta(days=5)
        report = back_tester.backtest(ShortAverageGood, "s", start_date, end_date)
        self.assertEqual(len(report.losses), 0)
        self.assertEqual(len(report.wins), 1)
        self.assertEqual(report.wins[0], 100)

    @mock.patch('portfolio.buy_prediction.ShortAverageGood.predict')
    def test_one_buy_n_sell_with_loss(self, mock_short_average_predict):
        algo_return_values = [
            PortfolioRecommendation("s", RecommendationType.BUY, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.SELL, None, 5),
        ]

        mock_short_average_predict.side_effect = algo_return_values

        back_tester = BackTester()
        end_date = datetime.date.today()
        start_date = end_date - relativedelta(days=5)
        report = back_tester.backtest(ShortAverageGood, "s", start_date, end_date)
        self.assertEqual(0, len(report.wins))
        self.assertEqual(1, len(report.losses))
        self.assertEqual(-50, report.losses[0])

    @mock.patch('portfolio.buy_prediction.ShortAverageGood.predict')
    def test_one_buy_n_no_sell_ends_in_NOOP_with_win(self, mock_short_average_predict):
        algo_return_values = [
            PortfolioRecommendation("s", RecommendationType.BUY, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 15),
        ]

        mock_short_average_predict.side_effect = algo_return_values

        back_tester = BackTester()
        end_date = datetime.date.today()
        start_date = end_date - relativedelta(days=5)
        report = back_tester.backtest(ShortAverageGood, "s", start_date, end_date)
        self.assertEqual(1, len(report.wins))
        self.assertEqual(0, len(report.losses))
        self.assertEqual(50, report.wins[0])

    @mock.patch('portfolio.buy_prediction.ShortAverageGood.predict')
    def test_one_buy_n_no_sell_ends_in_BUY_no_win_no_loss(self, mock_short_average_predict):
        algo_return_values = [
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.BUY, None, 15),
        ]

        mock_short_average_predict.side_effect = algo_return_values

        back_tester = BackTester()
        end_date = datetime.date.today()
        start_date = end_date - relativedelta(days=5)
        report = back_tester.backtest(ShortAverageGood, "s", start_date, end_date)
        self.assertEqual(0, len(report.wins))
        self.assertEqual(0, len(report.losses))


    @mock.patch('portfolio.buy_prediction.ShortAverageGood.predict')
    def test_one_buy_n_no_sell_with_loss(self, mock_short_average_predict):
        algo_return_values = [
            PortfolioRecommendation("s", RecommendationType.BUY, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 5),
        ]

        mock_short_average_predict.side_effect = algo_return_values

        back_tester = BackTester()
        end_date = datetime.date.today()
        start_date = end_date - relativedelta(days=5)
        report = back_tester.backtest(ShortAverageGood, "s", start_date, end_date)
        self.assertEqual(0, len(report.wins))
        self.assertEqual(1, len(report.losses))
        self.assertEqual(-50, report.losses[0])

    @mock.patch('portfolio.buy_prediction.ShortAverageGood.predict')
    def test_two_losses_one_win(self, mock_short_average_predict):
        algo_return_values = [
            PortfolioRecommendation("s", RecommendationType.BUY, None, 100),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.SELL, None, 25),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 5),
            PortfolioRecommendation("s", RecommendationType.BUY, None, 5),
            PortfolioRecommendation("s", RecommendationType.SELL, None, 10),
            PortfolioRecommendation("s", RecommendationType.BUY, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 5),
        ]

        mock_short_average_predict.side_effect = algo_return_values

        back_tester = BackTester()
        end_date = datetime.date.today()
        start_date = end_date - relativedelta(days=9)
        report = back_tester.backtest(ShortAverageGood, "s", start_date, end_date)
        self.assertEqual(1, len(report.wins))
        self.assertEqual(2, len(report.losses))
        self.assertEqual(-75, report.losses[0])
        self.assertEqual(-50, report.losses[1])
        self.assertEqual(100, report.wins[0])

    @mock.patch('portfolio.buy_prediction.ShortAverageGood.predict')
    def test_it_uses_orig_buy_value_to_determine_win_or_loss(self, mock_short_average_predict):
        algo_return_values = [
            PortfolioRecommendation("s", RecommendationType.BUY, None, 10),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 100),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 200),
            PortfolioRecommendation("s", RecommendationType.NOOP, None, 200),
            PortfolioRecommendation("s", RecommendationType.SELL, None, 160),
        ]

        mock_short_average_predict.side_effect = algo_return_values

        back_tester = BackTester()
        end_date = datetime.date.today()
        start_date = end_date - relativedelta(days=5)
        report = back_tester.backtest(ShortAverageGood, "s", start_date, end_date)
        self.assertEqual(0, len(report.wins))
        self.assertEqual(1, len(report.losses))
        self.assertEqual(-50, report.losses[0])

    def test_sell_price_changing(self):
        pass



if __name__ == '__main__':
    unittest.main()
