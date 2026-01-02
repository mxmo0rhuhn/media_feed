"""Secure YAML file operations."""

from pathlib import Path
from typing import Any

import yaml

from media_feed.security.sanitizer import validate_file_path
from media_feed.utils.constants import MAX_YAML_FILE_SIZE
from media_feed.utils.files import atomic_write, safe_read
from media_feed.utils.logger import get_logger

logger = get_logger(__name__)


def load_yaml(file_path: Path, allowed_directory: Path | None = None) -> dict[str, Any]:
    """Load YAML file securely.

    Args:
        file_path: Path to YAML file
        allowed_directory: Optional directory that must contain the file

    Returns:
        Parsed YAML data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If path validation fails or YAML is invalid
    """
    # Validate path
    validated_path = validate_file_path(file_path, allowed_directory)

    try:
        # Read with size limit
        content = safe_read(validated_path, max_size=MAX_YAML_FILE_SIZE)

        # Parse YAML
        data = yaml.safe_load(content)

        if not isinstance(data, dict):
            raise ValueError(f"YAML file {file_path} must contain a dictionary")

        logger.debug(f"Loaded YAML from {file_path}")
        return data

    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {file_path}: {e}") from e


def save_yaml(
    file_path: Path,
    data: dict[str, Any],
    allowed_directory: Path | None = None,
) -> None:
    """Save YAML file securely with atomic write.

    Args:
        file_path: Path to YAML file
        data: Data to save
        allowed_directory: Optional directory that must contain the file

    Raises:
        ValueError: If path validation fails
        OSError: If write fails
    """
    # Validate path
    if allowed_directory:
        validate_file_path(file_path, allowed_directory)

    try:
        # Serialize YAML
        yaml_content = yaml.dump(
            data,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

        # Atomic write
        atomic_write(file_path, yaml_content)

        logger.debug(f"Saved YAML to {file_path}")

    except Exception as e:
        raise OSError(f"Failed to save YAML to {file_path}: {e}") from e
