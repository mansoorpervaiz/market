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
        self.assertTrue(is_valid_symbol("GOOG"))
        self.assertTrue(is_valid_symbol("123"))
        self.assertTrue(is_valid_symbol("ABC123"))
        
        # Test invalid symbols
        self.assertFalse(is_valid_symbol("ABC@"))
        self.assertFalse(is_valid_symbol("ABC DEF"))
        self.assertFalse(is_valid_symbol(""))
        self.assertFalse(is_valid_symbol(None))
        self.assertFalse(is_valid_symbol(123))  # Not a string
    
    def test_calculate_percentage_change(self):
        # Test positive change
        self.assertEqual(calculate_percentage_change(100, 150), 50.0)
        
        # Test negative change
        self.assertEqual(calculate_percentage_change(100, 50), -50.0)
        
        # Test no change
        self.assertEqual(calculate_percentage_change(100, 100), 0.0)
        
        # Test with zero old value
        self.assertEqual(calculate_percentage_change(0, 100), 0.0)
        
        # Test with floating point values
        self.assertAlmostEqual(calculate_percentage_change(10.5, 15.75), 50.0)

if __name__ == '__main__':
    unittest.main()