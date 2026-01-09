"""Secure caching utilities."""

import hashlib
import time
from pathlib import Path
from typing import Optional

from media_feed.utils.logger import get_logger

logger = get_logger(__name__)

# Cache settings
CACHE_MAX_AGE_DAYS = 7


def get_cache_directory() -> Path:
    """Get the secure cache directory path.

    Returns:
        Path to cache directory in user's home directory
    """
    cache_dir = Path.home() / ".cache" / "media-feed"
    cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)  # User-only access
    return cache_dir


def get_cache_path(url: str, extension: str = "") -> Path:
    """Get cache file path for a URL.

    Args:
        url: URL to cache
        extension: Optional file extension

    Returns:
        Path to cache file
    """
    cache_dir = get_cache_directory()
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    filename = f"{url_hash}{extension}"
    return cache_dir / filename


def is_cache_valid(cache_path: Path, max_age_days: int = CACHE_MAX_AGE_DAYS) -> bool:
    """Check if cached file is still valid.

    Args:
        cache_path: Path to cached file
        max_age_days: Maximum age in days

    Returns:
        True if cache is valid, False otherwise
    """
    if not cache_path.exists():
        return False

    try:
        file_age = time.time() - cache_path.stat().st_mtime
        max_age_seconds = max_age_days * 24 * 60 * 60

        if file_age > max_age_seconds:
            logger.debug(f"Cache expired: {cache_path.name}")
            return False

        return True

    except OSError as e:
        logger.warning(f"Failed to check cache validity: {e}")
        return False


def read_cache(cache_path: Path, max_size: Optional[int] = None) -> Optional[bytes]:
    """Read cached content if valid.

    Args:
        cache_path: Path to cached file
        max_size: Maximum file size in bytes

    Returns:
        Cached content or None if invalid
    """
    if not is_cache_valid(cache_path):
        return None

    try:
        if max_size:
            file_size = cache_path.stat().st_size
            if file_size > max_size:
                logger.warning(
                    f"Cached file {cache_path.name} exceeds size limit "
                    f"({file_size} > {max_size})"
                )
                return None

        content = cache_path.read_bytes()
        logger.debug(f"Cache hit: {cache_path.name}")
        return content

    except OSError as e:
        logger.warning(f"Failed to read cache: {e}")
        return None


def write_cache(cache_path: Path, content: bytes) -> None:
    """Write content to cache file securely.

    Args:
        content: Content to cache
        cache_path: Path to cache file
    """
    try:
        # Ensure cache directory exists with secure permissions
        cache_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Write with secure permissions (user read/write only)
        cache_path.write_bytes(content)
        cache_path.chmod(0o600)

        logger.debug(f"Cached: {cache_path.name}")

    except OSError as e:
        logger.warning(f"Failed to write cache: {e}")


def clear_cache() -> int:
    """Clear all cached files.

    Returns:
        Number of files deleted
    """
    cache_dir = get_cache_directory()
    count = 0

    try:
        for cache_file in cache_dir.iterdir():
            if cache_file.is_file():
                cache_file.unlink()
                count += 1

        logger.info(f"Cleared {count} cached file(s)")
        return count

    except OSError as e:
        logger.error(f"Failed to clear cache: {e}")
        return count
