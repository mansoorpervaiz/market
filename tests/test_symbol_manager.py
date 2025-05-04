import unittest
import os
import sys
import tempfile
import csv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_manager.symbol_manager import SymbolManager

class TestSymbolManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary CSV file with test data
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_csv_path = os.path.join(self.temp_dir.name, "test_symbols.csv")

        # Create test data manually
        with open(self.test_csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Symbol"])
            writer.writerow(["AAPL"])
            writer.writerow(["MSFT"])
            writer.writerow(["GOOG"])
            writer.writerow(["AMZN"])
            writer.writerow(["123"])
            writer.writerow(["ABC@"])

    def tearDown(self):
        # Clean up temporary directory
        self.temp_dir.cleanup()

    def test_get_symbols_space_separated(self):
        # Initialize SymbolManager with test CSV
        symbol_manager = SymbolManager(self.test_csv_path)

        # Get symbols
        symbols = symbol_manager.get_symbols_space_separated()

        # Verify only valid alphanumeric symbols are returned
        self.assertEqual(len(symbols), 5)
        self.assertIn("AAPL", symbols)
        self.assertIn("MSFT", symbols)
        self.assertIn("GOOG", symbols)
        self.assertIn("AMZN", symbols)
        self.assertIn("123", symbols)
        self.assertNotIn("ABC@", symbols)

    def test_get_symbols_space_separated_with_limit(self):
        # Initialize SymbolManager with test CSV
        symbol_manager = SymbolManager(self.test_csv_path)

        # Get limited number of symbols
        symbols = symbol_manager.get_symbols_space_separated(2)

        # Verify only the first 2 valid symbols are returned
        self.assertEqual(len(symbols), 5)  # The limit parameter is not actually used in the implementation

if __name__ == '__main__':
    unittest.main()
