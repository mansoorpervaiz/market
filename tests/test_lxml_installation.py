# Copyright (c) 2025 Mansoor Pervaiz
# All rights reserved.
#
# This file is part of a proprietary software project.
# Unauthorized copying, distribution, modification, or use of this file,
# via any medium, is strictly prohibited unless explicit permission is granted
# by the author.
#
# For licensing inquiries, contact: mansoorpervaizdev@gmail.com

"""
Test script to verify that lxml is properly installed.
This script attempts to use pandas.read_html which requires lxml.
"""
import sys

def test_lxml():
    try:
        # First try to import lxml directly
        import lxml
        print(f"✅ lxml is installed (version: {lxml.__version__})")
        
        # Then try to import pandas and use read_html
        import pandas as pd
        print(f"✅ pandas is installed (version: {pd.__version__})")
        
        # Try to use read_html with a simple example
        url = 'https://en.wikipedia.org/wiki/Russell_1000_Index'
        print("Testing pandas.read_html with Wikipedia page...")
        tables = pd.read_html(url)
        print(f"✅ Successfully read {len(tables)} tables from Wikipedia")
        
        print("\nAll tests passed! Your environment is correctly set up.")
        return True
    
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("\nPlease install the missing dependency:")
        print("pip install lxml>=4.9.3")
        return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nThere was an issue with the test. Please check the error message above.")
        return False

if __name__ == "__main__":
    print("Testing lxml installation...\n")
    success = test_lxml()
    sys.exit(0 if success else 1)