"""CCC event API and search functionality."""

from pathlib import Path
from typing import Any

import requests

from media_feed.security.xml_parser import parse_xml_file
from media_feed.utils.cache import get_cache_path, read_cache, write_cache
from media_feed.utils.constants import HTTP_TIMEOUT, HTTP_USER_AGENT, MAX_DOWNLOAD_SIZE
from media_feed.utils.logger import get_logger

logger = get_logger(__name__)


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
                raise ValueError(
                    f"Downloaded content exceeds maximum size ({max_size} bytes)"
                )

        # Cache the result
        write_cache(cache_path, content)

        logger.info(f"Downloaded {len(content)} bytes from {url}")
        return content

    except requests.RequestException as e:
        logger.error(f"Failed to download {url}: {e}")
        raise


def map_track_to_categories(track: str, config: dict[str, Any]) -> list[str]:
    """Map CCC track to Apple Podcast categories.

    Args:
        track: CCC track name
        config: Configuration dictionary

    Returns:
        List of Apple Podcast categories
    """
    category_mapping = config.get("global", {}).get("category_mapping", {})

    # Invert the mapping: find all Apple categories that include this track
    categories = []
    for apple_category, ccc_tracks in category_mapping.items():
        if apple_category == "_default":
            continue
        if track in ccc_tracks:
            categories.append(apple_category)

    # If no match found, use default
    if not categories:
        categories = category_mapping.get("_default", ["Technology"])

    return categories


def search_ccc_talk(
    query: str,
    event_config: dict[str, Any],
    config: dict[str, Any],
    use_long_desc: bool = False,
) -> dict[str, Any] | None:
    """Search for CCC talk and return entry dictionary.

    Args:
        query: Search query
        event_config: Event configuration
        config: Global configuration
        use_long_desc: Use long description from Fahrplan

    Returns:
        Talk entry dictionary or None if not found

    Raises:
        requests.RequestException: If download fails
        Exception: If XML parsing fails
    """
    from media_feed.utils.constants import get_cache_directory

    cache_dir = get_cache_directory()

    try:
        # Download XMLs with caching
        fahrplan_content = download_with_cache(event_config["fahrplan_url"])
        media_content = download_with_cache(event_config["media_feed_url"])

        # Save to temp files for parsing
        fahrplan_file = cache_dir / "temp_fahrplan.xml"
        media_file = cache_dir / "temp_media.xml"

        fahrplan_file.write_bytes(fahrplan_content)
        media_file.write_bytes(media_content)

        # Parse XMLs securely
        fahrplan_dom = parse_xml_file(fahrplan_file)
        media_dom = parse_xml_file(media_file)

        # Clean up temp files
        fahrplan_file.unlink(missing_ok=True)
        media_file.unlink(missing_ok=True)

        # Search logic
        query_upper = query.upper()

        for fahrplan_node in fahrplan_dom.getElementsByTagName("title"):
            if not fahrplan_node.childNodes:
                continue

            title_text = fahrplan_node.childNodes[0].data

            if query_upper not in title_text.upper():
                continue

            # Extract from Fahrplan
            event = fahrplan_node.parentNode
            event_id = event.getAttribute("id")

            subtitle_elems = event.getElementsByTagName("subtitle")
            subtitle = (
                subtitle_elems[0].childNodes[0].data
                if subtitle_elems and subtitle_elems[0].childNodes
                else ""
            )

            # Extract speakers
            try:
                persons = event.getElementsByTagName("persons")[0]
                speakers = ", ".join(
                    [
                        p.childNodes[0].data
                        for p in persons.getElementsByTagName("person")
                        if p.childNodes
                    ]
                )
            except (IndexError, AttributeError):
                speakers = ""

            desc_elems = event.getElementsByTagName("description")
            description = (
                desc_elems[0].childNodes[0].data
                if desc_elems and desc_elems[0].childNodes
                else ""
            )

            # Extract track for category mapping
            track_elems = event.getElementsByTagName("track")
            track = (
                track_elems[0].childNodes[0].data
                if track_elems and track_elems[0].childNodes
                else ""
            )

            # Find in media feed
            for media_node in media_dom.getElementsByTagName("title"):
                if not media_node.childNodes:
                    continue

                if title_text.upper() not in media_node.childNodes[0].data.upper():
                    continue

                item = media_node.parentNode

                pub_elems = item.getElementsByTagName("pubDate")
                pub_date = (
                    pub_elems[0].childNodes[0].data
                    if pub_elems and pub_elems[0].childNodes
                    else ""
                )

                media_desc_elems = item.getElementsByTagName("description")
                media_desc = (
                    media_desc_elems[0].childNodes[0].data
                    if media_desc_elems and media_desc_elems[0].childNodes
                    else ""
                )

                enclosures = item.getElementsByTagName("enclosure")
                if not enclosures:
                    continue

                enclosure = enclosures[0]
                media_url = enclosure.getAttribute("url")
                media_length = enclosure.getAttribute("length")
                media_type = enclosure.getAttribute("type")

                web_url = f"{event_config['event_pattern_head']}{event_id}{event_config['event_pattern_tail']}"

                final_desc = description if use_long_desc else media_desc

                # Map track to categories
                categories = map_track_to_categories(track, config)

                logger.info(f"Found talk: {title_text}")

                return {
                    "title": title_text,
                    "published": pub_date,
                    "speakers": speakers,
                    "subtitle": subtitle,
                    "media_url": media_url,
                    "media_type": media_type,
                    "media_length": media_length,
                    "web_url": web_url,
                    "description": final_desc,
                    "categories": categories,
                }

        logger.info(f"No talk found matching query: {query}")
        return None

    except Exception as e:
        logger.error(f"Search failed: {e}")
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
