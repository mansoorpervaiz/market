# Configuration System

This document describes the configuration system for the market project.

## Overview

The market project uses a centralized configuration system that loads settings from environment variables with fallback to default values. This allows for easy configuration in different environments (development, testing, production) without modifying the code.

## Usage

To use the configuration system in your code:

```python
from config import config

# Access configuration values
api_key = config.ALPHA_VANTAGE_API_KEY
base_url = config.ALPHA_VANTAGE_BASE_URL
```

## Configuration Values

### Alpha Vantage API

| Configuration Key | Environment Variable | Default Value | Description |
|------------------|---------------------|---------------|-------------|
| ALPHA_VANTAGE_API_KEY | ALPHA_VANTAGE_API_KEY | "GNUI443FX0DTXC96" | API key for Alpha Vantage |
| ALPHA_VANTAGE_BASE_URL | ALPHA_VANTAGE_BASE_URL | "https://www.alphavantage.co/query" | Base URL for Alpha Vantage API |
| ALPHA_VANTAGE_RETRIES | ALPHA_VANTAGE_RETRIES | 3 | Number of retries for API requests |
| ALPHA_VANTAGE_RATE_LIMIT | ALPHA_VANTAGE_RATE_LIMIT | 75 | Maximum number of requests per minute |
| ALPHA_VANTAGE_RATE_PERIOD | ALPHA_VANTAGE_RATE_PERIOD | 60 | Rate limit period in seconds |

### Data Storage

| Configuration Key | Environment Variable | Default Value | Description |
|------------------|---------------------|---------------|-------------|
| DATA_ROOT_DIR | DATA_ROOT_DIR | "data" | Root directory for data storage |
| DATA_PICKLE_LOCATION | DATA_PICKLE_LOCATION | "data/daily/pickle" | Directory for pickle files |
| DATA_JSON_LOCATION | DATA_JSON_LOCATION | "data/daily/json" | Directory for JSON files |

### Logging

| Configuration Key | Environment Variable | Default Value | Description |
|------------------|---------------------|---------------|-------------|
| LOGS_DIR | LOGS_DIR | "logs" | Directory for log files |
| LOG_LEVEL_CONSOLE | LOG_LEVEL_CONSOLE | "INFO" | Log level for console output |
| LOG_LEVEL_FILE | LOG_LEVEL_FILE | "DEBUG" | Log level for file output |
| LOG_FILENAME_FORMAT | LOG_FILENAME_FORMAT | "market_%Y%m%d.log" | Format for log filenames |

## Setting Environment Variables

### Linux/macOS

```bash
export ALPHA_VANTAGE_API_KEY="your-api-key"
export LOG_LEVEL_CONSOLE="DEBUG"
```

### Windows

```cmd
set ALPHA_VANTAGE_API_KEY=your-api-key
set LOG_LEVEL_CONSOLE=DEBUG
```

### Using a .env File

You can also create a `.env` file in the project root directory with your environment variables:

```
ALPHA_VANTAGE_API_KEY=your-api-key
LOG_LEVEL_CONSOLE=DEBUG
```

Note: To use a .env file, you'll need to install the python-dotenv package and modify the config.py file to load variables from the .env file.

## Production Use

For production use, it's strongly recommended to set the ALPHA_VANTAGE_API_KEY environment variable rather than using the default value. The default API key is provided for development and testing purposes only.

## Validation

The configuration system validates that:

1. ALPHA_VANTAGE_API_KEY is set (not empty)
2. Numeric values (ALPHA_VANTAGE_RETRIES, ALPHA_VANTAGE_RATE_LIMIT, ALPHA_VANTAGE_RATE_PERIOD) are greater than 0
3. Log levels (LOG_LEVEL_CONSOLE, LOG_LEVEL_FILE) are valid log levels ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

If validation fails, a ConfigurationError is raised with a descriptive message.