"""Configuration management with validation."""

from pathlib import Path
from typing import Any

import yaml

from media_feed.utils.file_utils import MAX_YAML_FILE_SIZE, safe_read
from media_feed.utils.logger import get_logger

logger = get_logger(__name__)

# Configuration file path
CONFIG_FILE = Path("config.yaml")


class ConfigError(Exception):
    """Configuration validation error."""

    pass


def load_config(config_file: Path = CONFIG_FILE) -> dict[str, Any]:
    """Load and validate configuration file.

    Args:
        config_file: Path to config.yaml

    Returns:
        Validated configuration dictionary

    Raises:
        ConfigError: If configuration is invalid
        FileNotFoundError: If config file doesn't exist
    """
    try:
        content = safe_read(config_file, max_size=MAX_YAML_FILE_SIZE)
        config = yaml.safe_load(content)

        if not isinstance(config, dict):
            raise ConfigError("Configuration must be a dictionary")

        # Validate required sections
        validate_config(config)

        logger.info(f"Loaded configuration from {config_file}")
        return config

    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in configuration: {e}") from e
    except Exception as e:
        raise ConfigError(f"Failed to load configuration: {e}") from e


def validate_config(config: dict[str, Any]) -> None:
    """Validate configuration structure.

    Args:
        config: Configuration dictionary

    Raises:
        ConfigError: If configuration is invalid
    """
    # Check for required sections
    if "global" not in config:
        raise ConfigError("Missing 'global' section in configuration")

    if "events" not in config:
        raise ConfigError("Missing 'events' section in configuration")

    # Validate global section
    global_config = config["global"]
    required_global_keys = ["contact", "author", "link", "language"]

    for key in required_global_keys:
        if key not in global_config:
            logger.warning(f"Missing recommended global config key: {key}")

    # Validate contact
    if "contact" in global_config:
        contact = global_config["contact"]
        if not isinstance(contact, dict):
            raise ConfigError("global.contact must be a dictionary")
        if "email" not in contact:
            logger.warning("Missing 'email' in global.contact")

    # Validate events
    events = config["events"]
    if not isinstance(events, dict):
        raise ConfigError("events must be a dictionary")

    if not events:
        logger.warning("No events configured")
        return

    # Validate each event
    for event_key, event_config in events.items():
        validate_event_config(event_key, event_config)


def validate_event_config(event_key: str, event_config: dict[str, Any]) -> None:
    """Validate a single event configuration.

    Args:
        event_key: Event identifier
        event_config: Event configuration dictionary

    Raises:
        ConfigError: If event configuration is invalid
    """
    required_keys = [
        "year",
        "congress_number",
        "fahrplan_url",
        "media_feed_url",
    ]

    for key in required_keys:
        if key not in event_config:
            raise ConfigError(f"Missing required key '{key}' in event '{event_key}'")

    # Validate types
    if not isinstance(event_config["year"], int):
        raise ConfigError(f"Event '{event_key}': year must be an integer")

    if not isinstance(event_config["congress_number"], int):
        raise ConfigError(f"Event '{event_key}': congress_number must be an integer")

    # Validate URLs
    url_keys = ["fahrplan_url", "media_feed_url"]
    for key in url_keys:
        url = event_config[key]
        if not isinstance(url, str) or not url.startswith("http"):
            raise ConfigError(f"Event '{event_key}': {key} must be a valid HTTP(S) URL")

    # Validate that if one pattern key exists, both must exist
    has_pattern_head = "event_pattern_head" in event_config
    has_pattern_tail = "event_pattern_tail" in event_config

    if has_pattern_head != has_pattern_tail:
        raise ConfigError(
            f"Event '{event_key}': Both 'event_pattern_head' and 'event_pattern_tail' "
            f"must be provided together, or both omitted"
        )


def get_event_by_year(config: dict[str, Any], year: int) -> tuple[str, dict[str, Any]] | None:
    """Find event configuration by year.

    Args:
        config: Configuration dictionary
        year: Event year

    Returns:
        Tuple of (event_key, event_config) or None if not found
    """
    for event_key, event_config in config["events"].items():
        if event_config["year"] == year:
            return event_key, event_config
    return None


def get_latest_event(config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Get the latest event configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Tuple of (event_key, event_config)

    Raises:
        ConfigError: If no events configured
    """
    events = config["events"]
    if not events:
        raise ConfigError("No events configured")

    latest_key = max(events.keys(), key=lambda k: events[k]["year"])
    return latest_key, events[latest_key]


def calculate_congress_number(year: int, config: dict[str, Any]) -> int:
    """Calculate congress number for a given year.

    Uses the most recent event in config as a reference point and assumes
    annual congresses. This avoids hardcoding assumptions about COVID gaps.

    Args:
        year: Event year
        config: Configuration dictionary

    Returns:
        Calculated congress number

    Raises:
        ConfigError: If no events are configured
    """
    if "events" not in config or not config["events"]:
        raise ConfigError("No events configured - cannot calculate congress number")

    # Find the most recent event to use as reference
    latest_event_key, latest_event = get_latest_event(config)
    ref_year: int = int(latest_event["year"])
    ref_congress: int = int(latest_event["congress_number"])

    # Calculate offset from reference year (assumes annual congresses)
    year_offset = year - ref_year
    congress_number = ref_congress + year_offset

    return congress_number
