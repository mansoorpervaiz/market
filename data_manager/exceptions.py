"""
Custom exception classes for the data_manager module.

This module defines exception classes for different error types that can occur
in the data_manager module. These exceptions are organized in a hierarchical
structure to make error handling more consistent and specific.
"""

class DataManagerError(Exception):
    """Base exception class for all data_manager errors."""
    pass


class DataAccessError(DataManagerError):
    """Base exception class for data access errors."""
    pass


class DataDownloadError(DataAccessError):
    """Exception raised when there's an error downloading data."""
    pass


class APIError(DataDownloadError):
    """Exception raised when there's an error with the API."""
    pass


class RateLimitError(APIError):
    """Exception raised when the API rate limit is exceeded."""
    pass


class PremiumEndpointError(APIError):
    """Exception raised when trying to access a premium endpoint."""
    pass


class InvalidResponseError(APIError):
    """Exception raised when the API response is invalid or unexpected."""
    pass


class DataProcessingError(DataAccessError):
    """Exception raised when there's an error processing data."""
    pass


class DataFormatError(DataProcessingError):
    """Exception raised when the data format is invalid or unexpected."""
    pass


class DataNotFoundError(DataAccessError):
    """Exception raised when the requested data is not found."""
    pass


class SymbolError(DataManagerError):
    """Base exception class for symbol-related errors."""
    pass


class InvalidSymbolError(SymbolError):
    """Exception raised when a symbol is invalid."""
    pass


class SymbolNotFoundError(SymbolError):
    """Exception raised when a symbol is not found."""
    pass