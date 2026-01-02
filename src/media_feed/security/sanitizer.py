"""Input sanitization utilities."""

import re
from pathlib import Path
from typing import Optional


def sanitize_username(username: str, max_length: int = 50) -> str:
    """Sanitize username input.

    Args:
        username: Raw username input
        max_length: Maximum allowed length

    Returns:
        Sanitized username

    Raises:
        ValueError: If username is invalid
    """
    if not username:
        raise ValueError("Username cannot be empty")

    # Remove control characters and limit length
    sanitized = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", username)
    sanitized = sanitized.strip()[:max_length]

    if not sanitized:
        raise ValueError("Username contains only invalid characters")

    return sanitized


def sanitize_comment(comment: str, max_length: int = 500) -> str:
    """Sanitize comment input.

    Args:
        comment: Raw comment input
        max_length: Maximum allowed length

    Returns:
        Sanitized comment
    """
    if not comment:
        return ""

    # Remove control characters except newlines and tabs
    sanitized = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]", "", comment)
    sanitized = sanitized.strip()[:max_length]

    return sanitized


def validate_rating(rating: int) -> int:
    """Validate rating value.

    Args:
        rating: Rating value to validate

    Returns:
        Validated rating

    Raises:
        ValueError: If rating is out of range
    """
    if not isinstance(rating, int) or not 1 <= rating <= 5:
        raise ValueError("Rating must be an integer between 1 and 5")
    return rating


def sanitize_path_component(component: str) -> str:
    """Sanitize a path component to prevent path traversal.

    Args:
        component: Path component to sanitize

    Returns:
        Sanitized path component

    Raises:
        ValueError: If component contains path traversal attempts
    """
    if not component:
        raise ValueError("Path component cannot be empty")

    # Check for path traversal attempts
    if ".." in component or component.startswith("/") or component.startswith("~"):
        raise ValueError(f"Invalid path component (path traversal attempt): {component}")

    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>:"|?*\x00-\x1f]', "", component)

    if not sanitized:
        raise ValueError("Path component contains only invalid characters")

    return sanitized


def validate_file_path(file_path: Path, allowed_directory: Optional[Path] = None) -> Path:
    """Validate a file path to prevent path traversal attacks.

    Args:
        file_path: Path to validate
        allowed_directory: Optional directory that must contain the file

    Returns:
        Resolved absolute path

    Raises:
        ValueError: If path is invalid or outside allowed directory
    """
    try:
        # Resolve to absolute path
        resolved_path = file_path.resolve()

        # If allowed directory specified, ensure path is within it
        if allowed_directory:
            allowed_resolved = allowed_directory.resolve()
            if not str(resolved_path).startswith(str(allowed_resolved)):
                raise ValueError(
                    f"Path {file_path} is outside allowed directory {allowed_directory}"
                )

        return resolved_path

    except (OSError, RuntimeError) as e:
        raise ValueError(f"Invalid file path {file_path}: {e}") from e
