# Copyright (c) 2025 Mansoor Pervaiz
# All rights reserved.
#
# This file is part of a proprietary software project.
# Unauthorized copying, distribution, modification, or use of this file,
# via any medium, is strictly prohibited unless explicit permission is granted
# by the author.
#
# For licensing inquiries, contact: mansoorpervaizdev@gmail.com

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Try to import the modules
try:
    from ingesters.DailyDataIngester import process_symbol as daily_process_symbol
    from ingesters.IntradayDataIngester import process_symbol as intraday_process_symbol
    print("Successfully imported modules from ingesters directory.")
except ImportError as e:
    print(f"Error importing modules: {e}")