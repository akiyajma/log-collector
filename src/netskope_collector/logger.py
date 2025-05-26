"""
Logging utility module for the Netskope Event Collector.

This module provides a consistent logger setup across the application.
It configures loggers to output structured messages to standard output (stdout),
with optional log level control via the `LOG_LEVEL` environment variable.

Features:
---------
- Per-module logger retrieval using `get_logger(name)`
- Single handler per logger to avoid duplicate logs
- Configurable log level (default: INFO)
- Output includes timestamps, log level, module name, and message
"""

from __future__ import annotations

import logging
import os
import sys


_DEFAULT_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def get_logger(name: str) -> logging.Logger:
    """
    Retrieve a logger instance configured for the specified module name.

    This function ensures that:
    - Only one StreamHandler is attached per logger (no duplicate outputs)
    - Log messages are formatted uniformly across modules
    - Log level is configurable via the `LOG_LEVEL` environment variable

    Parameters:
    -----------
    name : str
        The name of the logger, typically the module's `__name__`.

    Returns:
    --------
    logging.Logger
        A logger instance with standardized settings.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(_DEFAULT_LEVEL)
        logger.propagate = False

    return logger
