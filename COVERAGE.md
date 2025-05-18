# Test Coverage Guide

This guide explains how to use the code coverage tool to measure and improve test coverage in the project.

## Prerequisites

- Python 3.6 or higher
- pip (Python package installer)
- Virtual environment (optional but recommended)

## Setup

The project includes a `requirements-dev.txt` file that contains all the development dependencies, including the coverage tool. To install these dependencies, run:

```bash
pip install -r requirements-dev.txt
```

## Running Tests with Coverage

The project includes a script that automates the process of running tests with coverage reporting. To use it:

1. Make sure the script is executable:
   ```bash
   chmod +x run_tests_with_coverage.sh
   ```

2. Run the script:
   ```bash
   ./run_tests_with_coverage.sh
   ```

This script will:
- Activate the virtual environment if it exists
- Install development dependencies
- Run all tests with coverage
- Generate a coverage report in the terminal
- Generate an HTML coverage report

## Manual Coverage Commands

If you prefer to run coverage commands manually, you can use the following:

1. Run tests with coverage:
   ```bash
   coverage run -m unittest discover -s tests
   ```

2. Generate a coverage report in the terminal:
   ```bash
   coverage report
   ```

3. Generate an HTML coverage report:
   ```bash
   coverage html
   ```

4. View the HTML report by opening `htmlcov/index.html` in your browser.

## Understanding the Coverage Report

The coverage report shows:

- **Name**: The name of the module or file
- **Stmts**: The number of statements in the file
- **Miss**: The number of statements that were not executed during the test
- **Cover**: The percentage of statements that were executed (coverage percentage)
- **Missing**: The line numbers of statements that were not executed

## Improving Test Coverage

To improve test coverage:

1. Focus on files with low coverage percentages
2. Add tests for the missing lines identified in the report
3. Pay special attention to critical components like the backtester, strategies, and data management

## Configuration

The coverage tool is configured using the `.coveragerc` file, which specifies:

- Which files to include in the coverage measurement
- Which files to exclude (e.g., tests, virtual environment)
- Which lines to exclude from coverage reporting (e.g., `if __name__ == '__main__':`)

You can modify this file to customize the coverage measurement according to your needs.

## Continuous Integration

For continuous integration, you can add the following step to your CI pipeline:

```yaml
- name: Run tests with coverage
  run: |
    pip install -r requirements-dev.txt
    coverage run -m unittest discover -s tests
    coverage report
    coverage xml  # Generate XML report for CI tools
```

This will ensure that test coverage is measured and reported in your CI pipeline.