"""
Utility functions for testing
"""

def is_valid_symbol(symbol):
    """
    Check if a symbol is valid (alphanumeric)
    
    Args:
        symbol (str): The symbol to check
        
    Returns:
        bool: True if the symbol is valid, False otherwise
    """
    if not isinstance(symbol, str):
        return False
    return symbol.isalnum()

def calculate_percentage_change(old_value, new_value):
    """
    Calculate the percentage change between two values
    
    Args:
        old_value (float): The original value
        new_value (float): The new value
        
    Returns:
        float: The percentage change
    """
    if old_value == 0:
        return 0
    return ((new_value - old_value) / old_value) * 100