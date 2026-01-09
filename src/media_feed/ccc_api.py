"""CCC event API and search functionality."""

from pathlib import Path
from typing import Any
from xml.dom.minidom import Document

from defusedxml import minidom

from media_feed.utils.cache_utils import get_cache_directory
from media_feed.utils.http_utils import download_with_cache
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


def normalize_title(title: str, remove_event_suffix: bool = True) -> str:
    """Normalize title for matching.

    Args:
        title: Title to normalize
        remove_event_suffix: Remove event ID suffix like (38c3)

    Returns:
        Normalized title
    """
    import re

    normalized = title.strip()

    # Remove event suffix like (38c3), (37c3), etc.
    if remove_event_suffix:
        normalized = re.sub(r"\s*\(\d+c3\)\s*$", "", normalized, flags=re.IGNORECASE)

    # Normalize whitespace
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip().upper()


def titles_match(fahrplan_title: str, media_title: str, threshold: float = 0.90) -> bool:
    """Check if titles match using multiple strategies.

    Tries progressively more lenient matching:
    1. Exact match (normalized)
    2. Substring match (current behavior)
    3. Token-based fuzzy match (handles word order and minor differences)

    Args:
        fahrplan_title: Title from fahrplan XML
        media_title: Title from media feed XML
        threshold: Similarity threshold for fuzzy matching (0-1)

    Returns:
        True if titles match
    """
    # Normalize both titles
    norm_fahrplan = normalize_title(fahrplan_title)
    norm_media = normalize_title(media_title)

    # Level 1: Exact match
    if norm_fahrplan == norm_media:
        logger.debug(f"Exact match: '{fahrplan_title}'")
        return True

    # Level 2: Bidirectional substring match
    # Check both directions because media feed may drop subtitles
    if norm_fahrplan in norm_media or norm_media in norm_fahrplan:
        logger.debug(f"Substring match: '{fahrplan_title}'")
        return True

    # Level 3: Token-based fuzzy matching
    # Split into tokens and calculate similarity
    # There are some occasions where words are mixed between titles:
    # "is" in fahrplan but "are" in media title
    fahrplan_tokens = set(norm_fahrplan.split())
    media_tokens = set(norm_media.split())

    # Calculate Jaccard similarity (intersection over union)
    if not fahrplan_tokens or not media_tokens:
        return False

    intersection = len(fahrplan_tokens & media_tokens)
    union = len(fahrplan_tokens | media_tokens)
    similarity = intersection / union if union > 0 else 0

    if similarity >= threshold:
        logger.debug(
            f"Fuzzy match (similarity: {similarity:.2f}): '{fahrplan_title}' ≈ '{media_title}'"
        )
        return True

    return False


def search_ccc_talk(
    query: str,
    event_config: dict[str, Any],
    config: dict[str, Any],
    use_long_desc: bool = False,
    event_key: str = "",
) -> dict[str, Any] | None:
    """Search for CCC talk and return entry dictionary.

    Args:
        query: Search query
        event_config: Event configuration
        config: Global configuration
        use_long_desc: Use long description from Fahrplan
        event_key: Event identifier for error messages (e.g., "38c3")

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
                desc_elems[0].childNodes[0].data if desc_elems and desc_elems[0].childNodes else ""
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

                media_title = media_node.childNodes[0].data
                if not titles_match(title_text, media_title):
                    continue

                item = media_node.parentNode

                pub_elems = item.getElementsByTagName("pubDate")
                pub_date = (
                    pub_elems[0].childNodes[0].data if pub_elems and pub_elems[0].childNodes else ""
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

                # Try to extract URL from fahrplan XML first (preferred method)
                url_elems = event.getElementsByTagName("url")
                if url_elems and url_elems[0].childNodes:
                    web_url = url_elems[0].childNodes[0].data
                    logger.debug(f"Extracted web_url from <url> tag: {web_url}")
                else:
                    # Fallback: construct URL from pattern (for backward compatibility)
                    if (
                        "event_pattern_head" in event_config
                        and "event_pattern_tail" in event_config
                    ):
                        web_url = (
                            f"{event_config['event_pattern_head']}"
                            f"{event_id}"
                            f"{event_config['event_pattern_tail']}"
                        )
                        logger.debug(f"Constructed web_url from pattern: {web_url}")
                    else:
                        # No URL available - this shouldn't happen with modern fahrplan XMLs
                        web_url = ""
                        logger.warning(
                            f"No <url> tag found and no event_pattern configured for "
                            f"event {event_id}"
                        )

                final_desc = description if use_long_desc else media_desc

                # Map track to categories
                categories = map_track_to_categories(track, config)
                # Use the first category as a string (media YAML format)
                category = categories[0] if categories else "Technology"

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
                    "category": category,
                }

        event_identifier = (
            f"{event_config['congress_number']}C3 ({event_config['year']})"
            if event_key
            else "event"
        )
        logger.warning(
            f"No talk found matching query '{query}' in {event_identifier}. "
            f"Searched fahrplan: {event_config.get('fahrplan_url', 'unknown')}"
        )
        return None

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise
