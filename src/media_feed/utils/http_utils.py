"""HTTP download utilities with caching."""

import requests

from media_feed.utils.cache_utils import get_cache_path, read_cache, write_cache
from media_feed.utils.logger import get_logger

logger = get_logger(__name__)

# HTTP settings
HTTP_TIMEOUT = 30
HTTP_USER_AGENT = "media-feed/1.0"
MAX_DOWNLOAD_SIZE = 100 * 1024 * 1024  # 100 MB


def download_with_cache(url: str, max_size: int = MAX_DOWNLOAD_SIZE) -> bytes:
    """Download content with caching.

    Args:
        url: URL to download
        max_size: Maximum download size in bytes

    Returns:
        Downloaded content

    Raises:
        requests.RequestException: If download fails
        ValueError: If content exceeds max_size
    """
    # Check cache first
    cache_path = get_cache_path(url, extension=".xml")
    cached_content = read_cache(cache_path, max_size=max_size)

    if cached_content is not None:
        return cached_content

    # Download
    logger.info(f"Downloading {url}")

    try:
        response = requests.get(
            url,
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": HTTP_USER_AGENT},
            stream=True,
        )
        response.raise_for_status()

        # Check content length
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_size:
            raise ValueError(
                f"Content size ({content_length} bytes) exceeds maximum ({max_size} bytes)"
            )

        # Download with size limit
        content = b""
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > max_size:
                raise ValueError(f"Downloaded content exceeds maximum size ({max_size} bytes)")

        # Cache the result
        write_cache(cache_path, content)

        logger.info(f"Downloaded {len(content)} bytes from {url}")
        return content

    except requests.RequestException as e:
        logger.error(f"Failed to download {url}: {e}")
        raise


def validate_url(url: str, timeout: int = HTTP_TIMEOUT) -> tuple[bool, str]:
    """Validate URL with HEAD request.

    Args:
        url: URL to validate
        timeout: Request timeout in seconds

    Returns:
        Tuple of (is_valid, message)
    """
    try:
        response = requests.head(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": HTTP_USER_AGENT},
        )

        if response.status_code == 200:
            return True, "OK"
        else:
            return False, f"HTTP {response.status_code}"

    except requests.RequestException as e:
        return False, str(e)


def check_url_exists(url: str, timeout: int = HTTP_TIMEOUT) -> bool:
    """Check if URL exists (returns 200).

    Args:
        url: URL to check
        timeout: Request timeout in seconds

    Returns:
        True if URL returns HTTP 200, False otherwise
    """
    try:
        response = requests.head(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": HTTP_USER_AGENT},
        )
        return response.status_code == 200
    except requests.RequestException:
        return False
