"""File operation utilities with security controls."""

import re
import tempfile
from pathlib import Path
from typing import Optional

# File size limits (in bytes)
MAX_YAML_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_XML_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def atomic_write(file_path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write content to a file atomically.

    Writes to a temporary file first, then renames it to the target path.
    This prevents file corruption if the process is interrupted.

    Args:
        file_path: Target file path
        content: Content to write
        encoding: File encoding (default: utf-8)

    Raises:
        OSError: If write or rename fails
    """
    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Create temp file in same directory as target
    fd, temp_path = tempfile.mkstemp(
        dir=file_path.parent, prefix=f".{file_path.name}.", suffix=".tmp"
    )

    try:
        # Write content to temp file
        with open(fd, "w", encoding=encoding) as f:
            f.write(content)

        # Atomic rename
        temp_path_obj = Path(temp_path)
        temp_path_obj.replace(file_path)

    except Exception:
        # Clean up temp file on error
        try:
            Path(temp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def safe_read(
    file_path: Path, max_size: Optional[int] = None, encoding: str = "utf-8"
) -> str:
    """Safely read a file with size validation.

    Args:
        file_path: File to read
        max_size: Maximum file size in bytes (optional)
        encoding: File encoding (default: utf-8)

    Returns:
        File contents

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file exceeds max_size
        OSError: If read fails
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if max_size:
        file_size = file_path.stat().st_size
        if file_size > max_size:
            raise ValueError(
                f"File {file_path} size ({file_size} bytes) exceeds "
                f"maximum allowed size ({max_size} bytes)"
            )

    return file_path.read_text(encoding=encoding)


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
