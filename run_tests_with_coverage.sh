#!/bin/bash

# Script to run tests with coverage reporting

# Check if virtual environment exists and activate it if it does
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Install development dependencies
echo "Installing development dependencies..."
pip install -r requirements-dev.txt

# Run tests with coverage
echo "Running tests with coverage..."
coverage run -m unittest discover -s tests

# Generate coverage report
echo "Generating coverage report..."
coverage report

# Generate HTML report (optional)
echo "Generating HTML coverage report..."
coverage html

echo "Coverage testing complete!"
echo "View the HTML report by opening htmlcov/index.html in your browser"