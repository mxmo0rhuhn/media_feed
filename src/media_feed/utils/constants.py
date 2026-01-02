"""Constants and configuration values."""

from pathlib import Path

# HTTP settings
HTTP_TIMEOUT = 30
HTTP_USER_AGENT = "media-feed/1.0"

# File size limits (in bytes)
MAX_YAML_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_XML_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_DOWNLOAD_SIZE = 100 * 1024 * 1024  # 100 MB

# Input validation limits
MAX_USERNAME_LENGTH = 50
MAX_COMMENT_LENGTH = 500
MAX_TITLE_LENGTH = 200

# Cache settings
CACHE_MAX_AGE_DAYS = 7

# File paths
CONFIG_FILE = Path("config.yaml")


def get_cache_directory() -> Path:
    """Get the secure cache directory path.

    Returns:
        Path to cache directory in user's home directory
    """
    cache_dir = Path.home() / ".cache" / "media-feed"
    cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)  # User-only access
    return cache_dir
