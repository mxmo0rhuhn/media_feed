"""Logging configuration."""

import logging
import sys
from typing import Optional

# Global logger configuration
_log_level = logging.WARNING
_configured = False


def configure_logging(level: int = logging.WARNING) -> None:
    """Configure global logging settings.

    Args:
        level: Logging level (default: WARNING)
    """
    global _log_level, _configured

    _log_level = level

    # Configure root logger
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    if not _configured:
        configure_logging()

    return logging.getLogger(name)


def set_log_level(level: int) -> None:
    """Set the global log level.

    Args:
        level: Logging level
    """
    global _log_level
    _log_level = level
    logging.getLogger().setLevel(level)
