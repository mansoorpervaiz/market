"""
Test script to verify that the configuration system is working correctly.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config import config

def test_config():
    """Test the configuration system."""
    print("Testing configuration system...")
    
    # Print all configuration values
    print("\nConfiguration values:")
    for key, value in config.to_dict().items():
        print(f"{key} = {value}")
    
    # Test that required directories exist
    print("\nVerifying directories:")
    for dir_path in [config.DATA_PICKLE_LOCATION, config.DATA_JSON_LOCATION, config.LOGS_DIR]:
        path = Path(dir_path)
        exists = path.exists()
        print(f"{dir_path}: {'exists' if exists else 'does not exist'}")
    
    # Test log level conversion
    print("\nTesting log level conversion:")
    for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        level_value = config.get_log_level(level)
        print(f"{level} = {level_value}")
    
    print("\nConfiguration test completed successfully!")

if __name__ == "__main__":
    # Set a test API key if not already set
    if not config.ALPHA_VANTAGE_API_KEY:
        print("WARNING: ALPHA_VANTAGE_API_KEY is not set. Using a test value for this run.")
        os.environ["ALPHA_VANTAGE_API_KEY"] = "test_api_key"
        # Reinitialize config to pick up the new environment variable
        from importlib import reload
        import config as config_module
        reload(config_module)
        from config import config
    
    test_config()