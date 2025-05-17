# Copyright (c) 2025 Mansoor Pervaiz
# All rights reserved.
#
# This file is part of a proprietary software project.
# Unauthorized copying, distribution, modification, or use of this file,
# via any medium, is strictly prohibited unless explicit permission is granted
# by the author.
#
# For licensing inquiries, contact: mansoorpervaizdev@gmail.com

import logging
import os
import sys
from datetime import datetime

from market.utils.config import config

# Configure the root logger
def configure_logger(name=None):
    """
    Configure and return a logger with the given name.
    If name is None, returns the root logger.
    """
    logger = logging.getLogger(name)

    # Only configure if handlers haven't been added yet
    if not logger.handlers:
        # Set the logging level
        logger.setLevel(config.get_log_level(config.LOG_LEVEL_CONSOLE))

        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )

        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(config.get_log_level(config.LOG_LEVEL_CONSOLE))

        # Create file handler
        log_filename = datetime.now().strftime(config.LOG_FILENAME_FORMAT)
        file_handler = logging.FileHandler(os.path.join(config.LOGS_DIR, log_filename))
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(config.get_log_level(config.LOG_LEVEL_FILE))

        # Add handlers to logger
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        # Prevent propagation to the root logger if this is a named logger
        if name:
            logger.propagate = False

    return logger

# Configure the root logger
root_logger = configure_logger()

def get_logger(name):
    """
    Get a logger with the specified name.
    This is the recommended way to get a logger in this project.
    """
    return configure_logger(name)
