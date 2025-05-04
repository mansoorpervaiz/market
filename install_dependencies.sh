#!/bin/bash

echo "Installing required dependencies..."

# Check if virtual environment exists and activate it if it does
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Install dependencies from requirements.txt
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Ensure lxml is installed (the main dependency causing issues)
echo "Ensuring lxml is installed..."
pip install lxml>=4.9.3

echo "Dependencies installation complete!"
echo "You can now run the data ingesters:"
echo "python DailyDataIngester.py"
echo "python IntradayDataIngester.py"