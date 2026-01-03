"""CCC event API and search functionality."""

from pathlib import Path
from typing import Any
from xml.dom.minidom import Document

try:
    from defusedxml import minidom
except ImportError:
    import warnings
    from xml.dom import minidom

    warnings.warn(
        "defusedxml not installed. XML parsing may be vulnerable to XXE attacks. "
        "Install with: pip install defusedxml",
        category=SecurityWarning,
        stacklevel=2,
    )

from media_feed.utils.cache_utils import get_cache_directory
from media_feed.utils.http_utils import download_with_cache, validate_url
from media_feed.utils.logger import get_logger

logger = get_logger(__name__)


def parse_xml_file(file_path: Path) -> Document:
    """Safely parse an XML file.

    Args:
        file_path: Path to the XML file

    Returns:
        Parsed XML Document

    Raises:
        FileNotFoundError: If file doesn't exist
        Exception: If XML parsing fails
    """
    if not file_path.exists():
        raise FileNotFoundError(f"XML file not found: {file_path}")

    return minidom.parse(str(file_path))


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
