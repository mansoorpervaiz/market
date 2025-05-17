# Data Manager Error Handling

This document describes the error handling patterns used in the Data Manager module.

## Exception Hierarchy

The Data Manager module uses a hierarchical exception structure to provide more specific error information:

```
DataManagerError
├── DataAccessError
│   ├── DataDownloadError
│   │   └── APIError
│   │       ├── RateLimitError
│   │       ├── PremiumEndpointError
│   │       └── InvalidResponseError
│   ├── DataProcessingError
│   │   └── DataFormatError
│   └── DataNotFoundError
└── SymbolError
    ├── InvalidSymbolError
    └── SymbolNotFoundError
```

## Using Exceptions

### Catching Exceptions

When catching exceptions, you can catch specific exception types or catch parent exception types to handle multiple related exceptions:

```python
try:
    data = await data_reader.get_data(symbol, start_date, end_date)
except DataNotFoundError as e:
    # Handle case where data is not found
    logger.warning(f"Data not found: {e}")
    # Fallback behavior...
except DataProcessingError as e:
    # Handle case where data could not be processed
    logger.error(f"Data processing error: {e}")
    # Error recovery...
except DataAccessError as e:
    # Handle any data access error not caught above
    logger.error(f"Data access error: {e}")
    # General error handling...
```

### Raising Exceptions

When raising exceptions, use the most specific exception type that applies to the error condition:

```python
if not os.path.exists(file_path):
    raise DataNotFoundError(f"File not found: {file_path}")

if not data_is_valid(data):
    raise DataFormatError(f"Invalid data format: {data_description}")
```

## Logging

The Data Manager module uses the project's logging system to log errors and warnings. Each module gets its own logger:

```python
from logger import get_logger

# Initialize logger
logger = get_logger(__name__)
```

### Log Levels

- **DEBUG**: Detailed information, typically useful only for diagnosing problems
- **INFO**: Confirmation that things are working as expected
- **WARNING**: An indication that something unexpected happened, or may happen in the near future
- **ERROR**: Due to a more serious problem, the software has not been able to perform a function
- **CRITICAL**: A serious error, indicating that the program itself may be unable to continue running

### Best Practices

1. **Always log exceptions**: When catching an exception, log it with appropriate context
2. **Use appropriate log levels**: Use ERROR for exceptions that prevent normal operation, WARNING for recoverable issues
3. **Include context**: Log messages should include relevant context (e.g., symbol, date range, file path)
4. **Don't log sensitive information**: Avoid logging API keys, passwords, or other sensitive information

## Example

```python
try:
    symbol_data_dict = await self.alpha_vantage_downloader.download(symbol)
    # Process data...
except RateLimitError as e:
    logger.warning(f"Rate limit exceeded for {symbol}: {e}")
    # Wait and retry...
except PremiumEndpointError as e:
    logger.error(f"Premium endpoint error for {symbol}: {e}")
    # Notify user of premium requirement...
except APIError as e:
    logger.error(f"API error for {symbol}: {e}")
    # General API error handling...
except Exception as e:
    logger.error(f"Unexpected error processing {symbol}: {e}")
    raise DataProcessingError(f"Unexpected error processing {symbol}: {e}") from e
```
