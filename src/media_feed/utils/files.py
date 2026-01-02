"""Atomic file operation utilities."""

import tempfile
from pathlib import Path
from typing import Optional


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
