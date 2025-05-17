# Market Analysis Project

## Overview

This project provides tools for financial market data collection, analysis, and portfolio optimization. It focuses on collecting data for Russell 1000 Index constituents and provides utilities for various trading strategies and backtesting.

## Installation

### Prerequisites

- Python 3.x
- Docker and Docker Compose (for deployment)

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd market
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:

   Option 1: Using the installation script:
   ```bash
   chmod +x install_dependencies.sh
   ./install_dependencies.sh
   ```

   Option 2: Using pip:
   ```bash
   pip install -r requirements.txt
   ```

## Russell 1000 Index Integration

The project has been updated to fetch stock symbols from the Russell 1000 Index instead of using Alpha Vantage API to get symbols from NYSE and NASDAQ exchanges. This change focuses the data collection on a specific set of large-cap U.S. stocks that are part of the Russell 1000 Index.

### Technical Implementation

1. The `SymbolManager` class in `data_manager/symbol_manager.py` includes a method `load_russell_1000_symbols()` that:
   - Fetches the Russell 1000 constituents from Wikipedia using pandas
   - Extracts the stock symbols from the table
   - Filters out non-alphanumeric symbols

2. The data ingesters (`ingesters/DailyDataIngester.py` and `ingesters/IntradayDataIngester.py`) use this method to load symbols.

### Testing Russell 1000 Integration

You can use the `test_russell_1000.py` script to test the Russell 1000 symbols functionality:

```bash
python test_russell_1000.py
```

This script will:
1. Load the Russell 1000 symbols from Wikipedia
2. Print the number of symbols loaded and the first 10 symbols
3. Save the symbols to a file named `russell_1000_symbols.txt`

### Notes on Russell 1000 Data

- The Wikipedia page structure may change over time, which could affect the symbol extraction. The code is designed to be somewhat flexible, but may need updates if the page structure changes significantly.
- The number of constituents in the Russell 1000 Index may vary slightly over time as companies are added or removed from the index.

## Resolving the lxml Dependency Issue

When running the data ingesters, you may encounter the following error:

```
ImportError: Missing optional dependency 'lxml'. Use pip or conda to install lxml.
```

This error occurs because pandas requires the lxml library to parse HTML tables when fetching Russell 1000 symbols from Wikipedia.

### System-Specific Installation Notes

On some systems, installing lxml might require additional system dependencies:

**Ubuntu/Debian:**
```bash
sudo apt-get install libxml2-dev libxslt-dev python-dev
```

**macOS (with Homebrew):**
```bash
brew install libxml2 libxslt
```

**Windows:**
On Windows, pip should install a pre-compiled binary of lxml, so no additional steps are typically needed.

### Verifying lxml Installation

Run the test script to verify that lxml is properly installed:

```bash
python test_lxml_installation.py
```

## Resolving NumPy Compatibility Issues

### IMPORTANT: NumPy Version Compatibility

When running tests or using the project, you may encounter the following error:

```
A module that was compiled using NumPy 1.x cannot be run in
NumPy 2.2.5 as it may crash. To support both 1.x and 2.x
versions of NumPy, modules must be compiled with NumPy 2.0.
Some module may need to rebuild instead e.g. with 'pybind11>=2.12'.
```

This error occurs because some dependencies in the project (particularly pyarrow) were compiled with NumPy 1.x and are not compatible with NumPy 2.x. You have two options to resolve this issue:

### Option 1: Downgrade NumPy (Simplest Solution)

The simplest solution is to downgrade NumPy to a version less than 2.0:

```bash
pip install numpy<2.0.0
```

After downgrading NumPy, reinstall the project dependencies to ensure all packages are compatible:

```bash
pip install -r requirements.txt
```

This will install a compatible version of NumPy that works with the project's dependencies and ensure that all other dependencies are correctly installed.

### Option 2: Use NumPy 2.x with Recompiled pyarrow

If you prefer to use NumPy 2.x, you can recompile pyarrow against NumPy 2.x as described in "Alternative Solution 2" below. This approach requires more setup but allows you to use the latest NumPy version.

### Verifying NumPy Version

To verify that you have the correct version of NumPy installed, run:

```bash
python -c "import numpy; print(numpy.__version__)"
```

The output should show a version less than 2.0.0 (e.g., 1.26.4).

### Option 2: Recompiling pyarrow with NumPy 2.x

If you prefer to use NumPy 2.x and recompile pyarrow to be compatible, follow these steps:

1. **Ensure you have the necessary build tools installed**:

   **Ubuntu/Debian**:
   ```bash
   sudo apt-get install -y build-essential cmake
   ```

   **macOS**:
   ```bash
   brew install cmake
   ```

   **Windows**:
   Install Visual Studio Build Tools and CMake.

2. **Install NumPy 2.x**:
   ```bash
   pip install numpy>=2.0.0
   ```

3. **Install pyarrow from source**:
   ```bash
   pip uninstall -y pyarrow
   pip install --no-binary pyarrow pyarrow
   ```

   This command forces pip to compile pyarrow from source against your installed NumPy version.

4. **Verify the installation**:
   ```bash
   python -c "import pyarrow; import numpy; print(f'PyArrow version: {pyarrow.__version__}, NumPy version: {numpy.__version__}')"
   ```

5. **Reinstall other dependencies**:
   ```bash
   pip install -r requirements.txt --no-deps
   ```

Note that compiling from source can take significant time and requires sufficient system resources. If you encounter build errors, you may need to install additional system dependencies or consider using Option 3 instead.

### Option 3: Separate Virtual Environment

If you need to use NumPy 2.x for other projects but don't want to recompile pyarrow, you can create a separate virtual environment for this project:

```bash
python -m venv .venv_numpy1
source .venv_numpy1/bin/activate  # On Windows: .venv_numpy1\Scripts\activate
pip install -r requirements.txt
```

This will create a new virtual environment with NumPy 1.x installed, which will be compatible with the project's dependencies.

## Parallel Processing Features

This project implements parallel processing to improve performance for data-intensive operations:

### Async IO

The codebase uses async IO throughout to handle I/O-bound operations efficiently:

- Data fetching operations run asynchronously
- Multiple backtests can run concurrently
- Strategy comparisons execute in parallel

### Parallel Processing with Dask

For CPU-bound operations, the project uses Dask to distribute work across multiple cores:

- Backtesting large datasets is parallelized using Dask
- Data processing for complex strategies can be distributed
- Large dataset operations benefit from Dask's out-of-core capabilities

### Usage Example

When creating a BackTester instance, you can control parallel processing:

```python
from backtester import BackTester
from data_manager.data_reader import DataReader

# Create a backtester with default parallel processing (enabled)
backtester = BackTester(DataReader())

# Disable dask parallel processing
backtester = BackTester(DataReader(), use_dask=False)

# Specify number of workers for dask
backtester = BackTester(DataReader(), n_workers=4)
```

### Performance Considerations

- For small datasets (< 1000 rows), parallel processing is automatically disabled to avoid overhead
- Dask is most beneficial for CPU-intensive operations on large datasets
- Async IO provides benefits even for smaller operations by allowing concurrent execution

## Usage

### Data Ingestion

The project provides two main data ingesters:

1. **Daily Data Ingester**:
   ```bash
   python ingesters/DailyDataIngester.py
   ```
   This script fetches daily stock data for Russell 1000 constituents.

2. **Intraday Data Ingester**:
   ```bash
   python ingesters/IntradayDataIngester.py
   ```
   This script fetches intraday stock data for Russell 1000 constituents.

### Data Storage and Optimization

The project implements several optimizations for efficient data storage and retrieval:

1. **Parquet Storage Format**:
   - Market data is stored in the Apache Parquet format, which offers:
     - Columnar storage for efficient querying
     - Snappy compression for reduced storage size
     - Better performance compared to pickle files
   - Legacy pickle format is maintained for backward compatibility

2. **Caching System**:
   - Implements a TTL (Time-To-Live) cache for frequently accessed data
   - Configurable cache size and expiration time
   - Significantly reduces disk I/O for repeated queries

3. **Indexing for Historical Data**:
   - Optimized indexing on date columns for efficient date range queries
   - Row group optimization for better query performance
   - Sorted data for faster filtering operations

To take advantage of these optimizations, make sure you have the required dependencies installed:
```bash
pip install pyarrow cachetools
```

These dependencies are included in the requirements.txt file.

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
   - The API key should be configured as an environment variable

### Docker Deployment

Deploy the development environment:
```bash
./deploy_dev.sh
```

## Testing

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

## Additional Resources

### Technical Analysis Methods
- Autoregression
- Moving average
- ARIMA (Autoregressive Integrated Moving Average)
- EWMA (Exponentially Weighted Moving Average)

### Educational Resources
- [Basic Stock Analysis](https://www.youtube.com/watch?v=57qAxRV577c)
- [Pandas Tutorial](https://www.youtube.com/watch?v=FKgtR_LO5N4)
- [NumPy Tutorial](https://youtu.be/kbBi1liIrFg)
- [Portfolio Optimization](https://www.youtube.com/watch?v=7kNwJYGghoE)

### Trading Insights
- Market cap can be approximated by multiplying open price and volume
- High correlation between companies in the same market can help spread risk
