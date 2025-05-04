# Russell 1000 Index Integration

This document describes the changes made to integrate Russell 1000 Index constituents into the data ingestion process.

## Overview

The project has been updated to fetch stock symbols from the Russell 1000 Index instead of using Alpha Vantage API to get symbols from NYSE and NASDAQ exchanges. This change focuses the data collection on a specific set of large-cap U.S. stocks that are part of the Russell 1000 Index.

## Changes Made

1. Added a new method `load_russell_1000_symbols()` to the `SymbolManager` class in `data_manager/symbol_manager.py` that:
   - Fetches the Russell 1000 constituents from Wikipedia using pandas
   - Extracts the stock symbols from the table
   - Filters out non-alphanumeric symbols

2. Updated `DailyDataIngester.py` and `IntradayDataIngester.py` to use the new method instead of loading symbols from Alpha Vantage API.

3. Added `lxml` to `requirements.txt` as it's required for pandas' `read_html` function to parse HTML tables.

## Usage

The data ingesters will now automatically fetch Russell 1000 symbols from Wikipedia when run:

```bash
python DailyDataIngester.py
python IntradayDataIngester.py
```

You can also use the `test_russell_1000.py` script to test the Russell 1000 symbols functionality:

```bash
python test_russell_1000.py
```

This script will:
1. Load the Russell 1000 symbols from Wikipedia
2. Print the number of symbols loaded and the first 10 symbols
3. Save the symbols to a file named `russell_1000_symbols.txt`

## Dependencies

Make sure to install the required dependencies:

```bash
pip install -r requirements.txt
```

This will install `lxml` which is required for parsing HTML tables from Wikipedia.

### lxml Dependency Issue

If you encounter an error related to the missing `lxml` dependency:

```
ImportError: Missing optional dependency 'lxml'. Use pip or conda to install lxml.
```

Please refer to the [LXML_DEPENDENCY_README.md](LXML_DEPENDENCY_README.md) for detailed instructions on resolving this issue.

We've provided several tools to help with the installation:

1. **Installation Script**: Run `./install_dependencies.sh` to automatically install all required dependencies.
2. **Test Script**: Run `python test_lxml_installation.py` to verify that lxml is properly installed.

On some systems, installing lxml might require additional system packages. See the [LXML_DEPENDENCY_README.md](LXML_DEPENDENCY_README.md) for system-specific instructions.

## Notes

- The Wikipedia page structure may change over time, which could affect the symbol extraction. The code is designed to be somewhat flexible, but may need updates if the page structure changes significantly.
- The number of constituents in the Russell 1000 Index may vary slightly over time as companies are added or removed from the index.
