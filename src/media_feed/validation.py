"""YAML validation for media feed files."""

from pathlib import Path
from typing import Any


class ValidationResult:
    """Container for validation warnings and errors."""

    def __init__(self):
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

        # Check feedback for missing ratings (ERROR)
        feedback_list = item.get("feedback", [])
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
