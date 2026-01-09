"""URL and XML validation utilities for CCC events."""

import xml.etree.ElementTree as ET
from typing import Optional

import requests

from media_feed.utils.http_utils import HTTP_TIMEOUT, HTTP_USER_AGENT


class ValidationResult:
    """Store validation results for a URL."""

    def __init__(self, url: str):
        self.url = url
        self.status_code: Optional[int] = None
        self.valid_xml: bool = False
        self.has_content: bool = False
        self.error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """Check if validation passed."""
        return (
            self.status_code == 200
            and self.valid_xml
            and self.has_content
            and not self.error
        )


def validate_fahrplan_xml(content: str) -> tuple[bool, bool, Optional[str]]:
    """Validate fahrplan schedule XML structure and content.

    Args:
        content: XML content as string

    Returns:
        Tuple of (is_valid_xml, has_events, error_message)
    """
    try:
        root = ET.fromstring(content)

        # Check if it's a schedule XML
        if root.tag != "schedule":
            return True, False, "Root element is not 'schedule'"

        # Check for conference info
        conference = root.find("conference")
        if conference is None:
            return True, False, "Missing 'conference' element"

        # Check for days with events
        days = root.findall("day")
        if not days:
            return True, False, "No 'day' elements found"

        # Check if there are actual events
        total_events = 0
        for day in days:
            rooms = day.findall("room")
            for room in rooms:
                events = room.findall("event")
                total_events += len(events)

        if total_events == 0:
            return True, False, "No events found in schedule"

        return True, True, None

    except ET.ParseError as e:
        return False, False, f"XML parse error: {str(e)}"
    except Exception as e:
        return False, False, f"Unexpected error: {str(e)}"


def validate_podcast_xml(content: str) -> tuple[bool, bool, Optional[str]]:
    """Validate podcast RSS feed XML structure and content.

    Args:
        content: XML content as string

    Returns:
        Tuple of (is_valid_xml, has_items, error_message)
    """
    try:
        root = ET.fromstring(content)

        # Check if it's an RSS feed
        if root.tag != "rss":
            return True, False, "Root element is not 'rss'"

        # Check for channel
        channel = root.find("channel")
        if channel is None:
            return True, False, "Missing 'channel' element"

        # Check for items
        items = channel.findall("item")
        if not items:
            return True, False, "No 'item' elements found in feed"

        # Validate at least one item has an enclosure (media file)
        has_enclosure = False
        for item in items:
            if item.find("enclosure") is not None:
                has_enclosure = True
                break

        if not has_enclosure:
            return True, True, "Warning: No items have media enclosures"

        return True, True, None

    except ET.ParseError as e:
        return False, False, f"XML parse error: {str(e)}"
    except Exception as e:
        return False, False, f"Unexpected error: {str(e)}"


def validate_url_with_content(
    url: str, url_type: str, timeout: int = HTTP_TIMEOUT
) -> ValidationResult:
    """Validate URL with HTTP request and content validation.

    Args:
        url: URL to validate
        url_type: Type of URL ('fahrplan' or 'podcast')
        timeout: Request timeout in seconds

    Returns:
        ValidationResult object
    """
    result = ValidationResult(url)

    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": HTTP_USER_AGENT},
        )
        result.status_code = response.status_code

        if response.status_code != 200:
            result.error = f"HTTP {response.status_code}"
            return result

        # Validate XML content based on type
        if url_type == "fahrplan":
            is_valid, has_content, error = validate_fahrplan_xml(response.text)
            result.valid_xml = is_valid
            result.has_content = has_content
            result.error = error
        elif url_type == "podcast":
            is_valid, has_content, error = validate_podcast_xml(response.text)
            result.valid_xml = is_valid
            result.has_content = has_content
            result.error = error
        else:
            result.error = f"Unknown URL type: {url_type}"

    except requests.RequestException as e:
        result.error = str(e)

    return result


def validate_event_urls(
    fahrplan_url: str, podcast_url: str, timeout: int = HTTP_TIMEOUT
) -> tuple[ValidationResult, ValidationResult]:
    """Validate both fahrplan and podcast URLs for an event.

    Args:
        fahrplan_url: Fahrplan schedule URL
        podcast_url: Podcast feed URL
        timeout: Request timeout in seconds

    Returns:
        Tuple of (fahrplan_result, podcast_result)
    """
    fahrplan_result = validate_url_with_content(fahrplan_url, "fahrplan", timeout)
    podcast_result = validate_url_with_content(podcast_url, "podcast", timeout)
    return fahrplan_result, podcast_result
