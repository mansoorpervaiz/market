# Project Development Guidelines

This document provides guidelines and information for developing and maintaining this project.

## Build/Configuration Instructions

### Environment Setup

1. **Python Environment**:
   - The project requires Python 3.x
   - Create a virtual environment:
     ```bash
     python -m venv .venv
     source .venv/bin/activate  # On Windows: .venv\Scripts\activate
     ```
   - Install dependencies:
     ```bash
     pip install -r requirements.txt
     ```

2. **Docker Environment**:
   - The project uses Docker for deployment
   - Make sure Docker and Docker Compose are installed
   - Deploy the development environment:
     ```bash
     ./deploy_dev.sh
     ```

### Configuration

1. **Database Configuration**:
   - The project uses InfluxDB for time-series data storage
   - Default credentials are set in `deploy_dev.sh`:
     ```bash
     export INFLUXDB_USERNAME=admin
     export INFLUXDB_PASSWORD=admin
     ```
   - For production, modify these credentials and keep them secure

2. **Alpha Vantage API**:
   - The project uses Alpha Vantage API for financial data
   - The API key is hardcoded in `data_manager/alpha_vantage.py`
   - For production, consider moving this to an environment variable

## Testing Information

### Running Tests

1. **Running All Tests**:
   ```bash
   cd tests
   python -m unittest discover
   ```

2. **Running Specific Tests**:
   ```bash
   cd tests
   python -m unittest test_utils.py
   ```

### Writing Tests

1. **Test Structure**:
   - Tests are organized in the `tests` directory
   - Test files should be named `test_*.py`
   - Use the `unittest` framework for tests
   - Add the project root to the Python path in test files:
     ```python
     import sys
     import os
     sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
     ```

2. **Test Example**:
   ```python
   import unittest
   import sys
   import os
   
   # Add the project root to the Python path
   sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
   
   from tests.utils import is_valid_symbol, calculate_percentage_change
   
   class TestUtils(unittest.TestCase):
       def test_is_valid_symbol(self):
           # Test valid symbols
           self.assertTrue(is_valid_symbol("AAPL"))
           self.assertTrue(is_valid_symbol("MSFT"))
           
           # Test invalid symbols
           self.assertFalse(is_valid_symbol("ABC@"))
           self.assertFalse(is_valid_symbol(None))
   
   if __name__ == '__main__':
       unittest.main()
   ```

3. **Mocking**:
   - Use the `mock` module for mocking dependencies
   - Example from `test_back_tester.py`:
     ```python
     @mock.patch('portfolio.buy_prediction.ShortAverageGood.predict')
     def test_one_buy_n_sell_with_win(self, mock_short_average_predict):
         # Set up mock return values
         mock_short_average_predict.side_effect = [...]
         
         # Test the function
         back_tester = BackTester()
         report = back_tester.backtest(...)
         
         # Assert the results
         self.assertEqual(len(report.wins), 1)
     ```

## Additional Development Information

### Code Style

1. **Python Style**:
   - Follow PEP 8 guidelines
   - Use 4 spaces for indentation
   - Use docstrings for classes and functions
   - Use type hints where appropriate

2. **Project Structure**:
   - Organize code by module/component (e.g., `portfolio`, `data_manager`)
   - Keep related functionality together
   - Use relative imports within modules

### Known Issues

1. **Import Issues**:
   - There appears to be a mismatch between imports and actual class names:
     - `data_reader.py` imports `AlphaVantageDownloader` but the class is named `AsyncAlphaVantageDownloader`
   - This should be fixed to ensure proper functionality

### Data Management

1. **Data Storage**:
   - Financial data is stored in pickle files in the `data` directory
   - Data is fetched from Alpha Vantage API when not available locally
   - The `DataReader` class handles data loading, saving, and retrieval

2. **Symbol Management**:
   - The `SymbolManager` class handles stock symbols
   - Symbols are loaded from CSV files in the `data` directory

### Portfolio Analysis

1. **Trading Strategies**:
   - Trading strategies are implemented in the `portfolio` module
   - The `ShortAverageGood` and `BuyAtSMA200` classes implement different strategies
   - The `BackTester` class is used to test strategies on historical data