import unittest
import sys
import os
import tempfile
from unittest import mock
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import Configuration, config
import logging


class TestConfiguration(unittest.TestCase):
    """Test cases for the Configuration class."""

    def setUp(self):
        """Set up test fixtures."""
        # Save original environment variables
        self.original_env = os.environ.copy()

        # Create a temporary directory for test data
        self.temp_dir = tempfile.TemporaryDirectory()

        # Set up test environment variables
        os.environ['DATA_PICKLE_LOCATION'] = os.path.join(self.temp_dir.name, 'data_pickle')
        os.environ['DATA_JSON_LOCATION'] = os.path.join(self.temp_dir.name, 'data_json')
        os.environ['LOGS_DIR'] = os.path.join(self.temp_dir.name, 'logs')
        os.environ['ALPHA_VANTAGE_API_KEY'] = 'test_api_key'
        os.environ['ALPHA_VANTAGE_BASE_URL'] = 'https://test.alphavantage.co/query'
        os.environ['ALPHA_VANTAGE_RETRIES'] = '3'
        os.environ['ALPHA_VANTAGE_RATE_LIMIT'] = '5'
        os.environ['ALPHA_VANTAGE_RATE_PERIOD'] = '60'
        os.environ['LOG_LEVEL'] = 'INFO'

    def tearDown(self):
        """Clean up after tests."""
        # Restore original environment variables
        os.environ.clear()
        os.environ.update(self.original_env)

        # Clean up temporary directory
        self.temp_dir.cleanup()

    def test_configuration_initialization(self):
        """Test that Configuration initializes correctly from environment variables."""
        # Create a new Configuration instance
        config = Configuration()

        # Verify that values were loaded from environment variables
        self.assertEqual(config.DATA_PICKLE_LOCATION, os.environ['DATA_PICKLE_LOCATION'])
        self.assertEqual(config.DATA_JSON_LOCATION, os.environ['DATA_JSON_LOCATION'])
        self.assertEqual(config.LOGS_DIR, os.environ['LOGS_DIR'])
        self.assertEqual(config.ALPHA_VANTAGE_API_KEY, os.environ['ALPHA_VANTAGE_API_KEY'])
        self.assertEqual(config.ALPHA_VANTAGE_BASE_URL, os.environ['ALPHA_VANTAGE_BASE_URL'])
        self.assertEqual(config.ALPHA_VANTAGE_RETRIES, int(os.environ['ALPHA_VANTAGE_RETRIES']))
        self.assertEqual(config.ALPHA_VANTAGE_RATE_LIMIT, int(os.environ['ALPHA_VANTAGE_RATE_LIMIT']))
        self.assertEqual(config.ALPHA_VANTAGE_RATE_PERIOD, int(os.environ['ALPHA_VANTAGE_RATE_PERIOD']))
        self.assertEqual(config.LOG_LEVEL, os.environ['LOG_LEVEL'])

    def test_configuration_default_values(self):
        """Test that Configuration uses default values when environment variables are not set."""
        # Clear relevant environment variables
        for key in ['DATA_PICKLE_LOCATION', 'DATA_JSON_LOCATION', 'LOGS_DIR', 
                   'ALPHA_VANTAGE_RETRIES', 'ALPHA_VANTAGE_RATE_LIMIT', 
                   'ALPHA_VANTAGE_RATE_PERIOD', 'LOG_LEVEL']:
            if key in os.environ:
                del os.environ[key]

        # Create a new Configuration instance
        config = Configuration()

        # Verify that default values were used
        self.assertEqual(config.DATA_PICKLE_LOCATION, os.path.join(os.getcwd(), 'data'))
        self.assertEqual(config.DATA_JSON_LOCATION, os.path.join(os.getcwd(), 'data_json'))
        self.assertEqual(config.LOGS_DIR, os.path.join(os.getcwd(), 'logs'))
        self.assertEqual(config.ALPHA_VANTAGE_RETRIES, 5)  # Default value
        self.assertEqual(config.ALPHA_VANTAGE_RATE_LIMIT, 5)  # Default value
        self.assertEqual(config.ALPHA_VANTAGE_RATE_PERIOD, 60)  # Default value
        self.assertEqual(config.LOG_LEVEL, 'INFO')  # Default value

    def test_directory_creation(self):
        """Test that Configuration creates necessary directories."""
        # Create a new Configuration instance
        config = Configuration()

        # Verify that directories were created
        self.assertTrue(os.path.exists(config.DATA_PICKLE_LOCATION))
        self.assertTrue(os.path.exists(config.DATA_JSON_LOCATION))
        self.assertTrue(os.path.exists(config.LOGS_DIR))

    def test_get_log_level(self):
        """Test the get_log_level method."""
        # Create a new Configuration instance
        config = Configuration()

        # Test valid log levels
        self.assertEqual(config.get_log_level('DEBUG'), logging.DEBUG)
        self.assertEqual(config.get_log_level('INFO'), logging.INFO)
        self.assertEqual(config.get_log_level('WARNING'), logging.WARNING)
        self.assertEqual(config.get_log_level('ERROR'), logging.ERROR)
        self.assertEqual(config.get_log_level('CRITICAL'), logging.CRITICAL)

        # Test invalid log level (should default to INFO)
        self.assertEqual(config.get_log_level('INVALID'), logging.INFO)

    def test_to_dict(self):
        """Test the to_dict method."""
        # Create a new Configuration instance
        config = Configuration()

        # Get the dictionary representation
        config_dict = config.to_dict()

        # Verify that it contains all the expected keys
        expected_keys = [
            'DATA_PICKLE_LOCATION', 'DATA_JSON_LOCATION', 'LOGS_DIR',
            'ALPHA_VANTAGE_API_KEY', 'ALPHA_VANTAGE_BASE_URL',
            'ALPHA_VANTAGE_RETRIES', 'ALPHA_VANTAGE_RATE_LIMIT',
            'ALPHA_VANTAGE_RATE_PERIOD', 'LOG_LEVEL'
        ]
        for key in expected_keys:
            self.assertIn(key, config_dict)

        # Verify that values match
        self.assertEqual(config_dict['DATA_PICKLE_LOCATION'], config.DATA_PICKLE_LOCATION)
        self.assertEqual(config_dict['ALPHA_VANTAGE_API_KEY'], config.ALPHA_VANTAGE_API_KEY)

    @mock.patch('os.makedirs')
    def test_validation_error_handling(self, mock_makedirs):
        """Test that Configuration handles validation errors gracefully."""
        # Make os.makedirs raise an exception
        mock_makedirs.side_effect = PermissionError("Permission denied")

        # Create a new Configuration instance and expect no exception
        try:
            config = Configuration()
            # If we get here, the test passes because no exception was raised
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Configuration initialization raised an exception: {e}")


if __name__ == '__main__':
    unittest.main()
