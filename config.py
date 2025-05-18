"""
Configuration module for the market project.

This module provides a centralized configuration system that loads settings from
environment variables with fallback to default values. It also includes validation
for configuration values.

Usage:
    from config import config

    # Access configuration values
    api_key = config.ALPHA_VANTAGE_API_KEY
    base_url = config.ALPHA_VANTAGE_BASE_URL
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigurationError(Exception):
    """Exception raised for configuration errors."""
    pass


class Configuration:
    """
    Configuration class that loads settings from environment variables
    with fallback to default values.
    """

    def __init__(self):
        """Initialize the configuration and validate required values."""
        # Alpha Vantage API configuration
        # Default API key for development/testing - should be overridden in production
        self.ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "GNUI443FX0DTXC96")
        self.ALPHA_VANTAGE_BASE_URL = os.environ.get("ALPHA_VANTAGE_BASE_URL", "https://www.alphavantage.co/query")
        self.ALPHA_VANTAGE_RETRIES = int(os.environ.get("ALPHA_VANTAGE_RETRIES", "5"))
        self.ALPHA_VANTAGE_RATE_LIMIT = int(os.environ.get("ALPHA_VANTAGE_RATE_LIMIT", "5"))
        self.ALPHA_VANTAGE_RATE_PERIOD = int(os.environ.get("ALPHA_VANTAGE_RATE_PERIOD", "60"))

        # Data storage configuration
        self.DATA_ROOT_DIR = os.environ.get("DATA_ROOT_DIR", "data")
        self.DATA_PICKLE_LOCATION = os.environ.get(
            "DATA_PICKLE_LOCATION", 
            os.path.join(self.DATA_ROOT_DIR, "daily", "pickle")
        )
        self.DATA_JSON_LOCATION = os.environ.get(
            "DATA_JSON_LOCATION", 
            os.path.join(self.DATA_ROOT_DIR, "daily", "json")
        )
        self.DATA_PARQUET_LOCATION = os.environ.get(
            "DATA_PARQUET_LOCATION", 
            os.path.join(self.DATA_ROOT_DIR, "daily", "parquet")
        )
        # Cache configuration
        self.CACHE_MAX_SIZE = int(os.environ.get("CACHE_MAX_SIZE", "100"))
        self.CACHE_TTL = int(os.environ.get("CACHE_TTL", "3600"))  # Time-to-live in seconds

        # Logging configuration
        self.LOGS_DIR = os.environ.get("LOGS_DIR", os.path.join(os.getcwd(), "logs"))
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
        self.LOG_LEVEL_CONSOLE = os.environ.get("LOG_LEVEL_CONSOLE", "INFO")
        self.LOG_LEVEL_FILE = os.environ.get("LOG_LEVEL_FILE", "DEBUG")
        self.LOG_FILENAME_FORMAT = os.environ.get("LOG_FILENAME_FORMAT", "market_%Y%m%d.log")

        self._validate_configuration()
        self._ensure_directories_exist()

        # Warn if using default API key
        if self.ALPHA_VANTAGE_API_KEY == "GNUI443FX0DTXC96":
            import warnings
            warnings.warn(
                "Using default Alpha Vantage API key. "
                "For production use, set the ALPHA_VANTAGE_API_KEY environment variable.",
                UserWarning
            )

    def _validate_configuration(self):
        """Validate that all required configuration values are set."""
        if not self.ALPHA_VANTAGE_API_KEY:
            raise ConfigurationError(
                "ALPHA_VANTAGE_API_KEY is not set. "
                "Please set it as an environment variable or in a .env file."
            )

        # Validate numeric values
        if self.ALPHA_VANTAGE_RETRIES <= 0:
            raise ConfigurationError("ALPHA_VANTAGE_RETRIES must be greater than 0")

        if self.ALPHA_VANTAGE_RATE_LIMIT <= 0:
            raise ConfigurationError("ALPHA_VANTAGE_RATE_LIMIT must be greater than 0")

        if self.ALPHA_VANTAGE_RATE_PERIOD <= 0:
            raise ConfigurationError("ALPHA_VANTAGE_RATE_PERIOD must be greater than 0")

        # Validate log levels
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.LOG_LEVEL_CONSOLE not in valid_log_levels:
            raise ConfigurationError(f"LOG_LEVEL_CONSOLE must be one of {valid_log_levels}")

        if self.LOG_LEVEL_FILE not in valid_log_levels:
            raise ConfigurationError(f"LOG_LEVEL_FILE must be one of {valid_log_levels}")

    def _ensure_directories_exist(self):
        """Ensure that all required directories exist."""
        try:
            Path(self.DATA_PICKLE_LOCATION).mkdir(parents=True, exist_ok=True)
            Path(self.DATA_JSON_LOCATION).mkdir(parents=True, exist_ok=True)
            Path(self.DATA_PARQUET_LOCATION).mkdir(parents=True, exist_ok=True)
            Path(self.LOGS_DIR).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            # Use the root logger to ensure the warning is captured by assertLogs
            import logging
            logging.getLogger().setLevel(logging.WARNING)
            logging.getLogger().warning(f"Failed to create directory: {str(e)}")

    def get_log_level(self, level_name: str) -> int:
        """Convert a log level name to its corresponding integer value."""
        try:
            return getattr(logging, level_name)
        except AttributeError:
            # Return INFO as default for invalid log levels
            return logging.INFO

    def to_dict(self) -> Dict[str, Any]:
        """Convert the configuration to a dictionary."""
        return {
            key: value for key, value in self.__dict__.items()
            if not key.startswith('_') and key.isupper()
        }

    def __str__(self) -> str:
        """Return a string representation of the configuration."""
        return str(self.to_dict())


# Create a singleton instance of the configuration
config = Configuration()
