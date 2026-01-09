"""YAML file operations and validation."""

from pathlib import Path
from typing import Any

import yaml

from media_feed.utils.file_utils import (
    MAX_YAML_FILE_SIZE,
    atomic_write,
    safe_read,
    validate_file_path,
)
from media_feed.utils.logger import get_logger

logger = get_logger(__name__)


class ValidationResult:
    """Container for validation warnings and errors."""

    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def add_warning(self, message: str) -> None:
        """Add a validation warning."""
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        """Add a validation error."""
        self.errors.append(message)

    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0


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


def validate_yaml_data(data: dict[str, Any], yaml_file: Path) -> ValidationResult:
    """Validate YAML data for missing categories and invalid feedback.

    Args:
        data: Loaded YAML data dictionary
        yaml_file: Path to the YAML file (for error messages)

    Returns:
        ValidationResult with warnings and errors
    """
    result = ValidationResult()

    # Process all feed items
    if "feed" not in data or not data["feed"]:
        return result

    for idx, item in enumerate(data["feed"], start=1):
        title = item.get("title", f"Untitled (item {idx})")

        # Check for missing category (WARNING)
        if "category" not in item or not item["category"]:
            result.add_warning(f"Talk '{title}' is missing a category")

        # Check for missing feedback (WARNING)
        feedback_list = item.get("feedback", [])
        if not feedback_list:
            result.add_warning(f"Talk '{title}' has no feedback")

        # Check feedback for missing ratings (ERROR)
        for feedback_idx, feedback in enumerate(feedback_list, start=1):
            if "rating" not in feedback or feedback["rating"] is None:
                username = feedback.get("username", "Anonymous")
                comment_preview = (
                    feedback.get("comment", "")[:40] + "..."
                    if len(feedback.get("comment", "")) > 40
                    else feedback.get("comment", "")
                )
                result.add_error(
                    f"Talk '{title}': Feedback #{feedback_idx} (by {username}) "
                    f"is missing a rating{f': {comment_preview}' if comment_preview else ''}"
                )

    return result
