# Resolving the lxml Dependency Issue

## Problem

When running the data ingesters (DailyDataIngester.py or IntradayDataIngester.py), you may encounter the following error:

```
ImportError: Missing optional dependency 'lxml'. Use pip or conda to install lxml.
```

This error occurs because pandas requires the lxml library to parse HTML tables when fetching Russell 1000 symbols from Wikipedia.

## Solution

### Option 1: Using the Installation Script

We've provided an installation script that will install all required dependencies, including lxml:

```bash
# Make the script executable
chmod +x install_dependencies.sh

# Run the script
./install_dependencies.sh
```

### Option 2: Manual Installation

If you prefer to install lxml manually, you can use pip:

```bash
# If using a virtual environment, activate it first
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install lxml
pip install lxml>=4.9.3
```

### Option 3: Using requirements.txt

The lxml dependency is already included in the requirements.txt file. You can install all dependencies by running:

```bash
pip install -r requirements.txt
```

## Notes

- On some systems, installing lxml might require additional system dependencies. If you encounter issues, you might need to install system packages:

  **Ubuntu/Debian:**
  ```bash
  sudo apt-get install libxml2-dev libxslt-dev python-dev
  ```

  **macOS (with Homebrew):**
  ```bash
  brew install libxml2 libxslt
  ```

  **Windows:**
  On Windows, pip should install a pre-compiled binary of lxml, so no additional steps are typically needed.

- After installing lxml, you should be able to run the data ingesters without any issues.