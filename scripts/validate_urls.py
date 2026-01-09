#!/usr/bin/env python3
"""Comprehensive URL validation for CCC congress events.

This script validates both the HTTP accessibility and content structure
of schedule and podcast feed URLs for all configured CCC events.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import requests
import yaml


class ValidationResult:
    """Store validation results for an event."""

    def __init__(self, event_id: str):
        self.event_id = event_id
        self.fahrplan_status: Optional[int] = None
        self.fahrplan_valid_xml: bool = False
        self.fahrplan_has_events: bool = False
        self.fahrplan_error: Optional[str] = None

        self.podcast_status: Optional[int] = None
        self.podcast_valid_xml: bool = False
        self.podcast_has_items: bool = False
        self.podcast_error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """Check if all validations passed."""
        return (
            self.fahrplan_status == 200
            and self.fahrplan_valid_xml
            and self.fahrplan_has_events
            and self.podcast_status == 200
            and self.podcast_valid_xml
            and self.podcast_has_items
            and not self.fahrplan_error
            and not self.podcast_error
        )

    def __str__(self) -> str:
        """Format validation results."""
        lines = [f"\n{'=' * 70}", f"Event: {self.event_id}", f"{'=' * 70}"]

        # Fahrplan results
        lines.append("\n📅 Fahrplan Schedule:")
        lines.append(f"  HTTP Status: {self.fahrplan_status or 'N/A'}")
        lines.append(f"  Valid XML: {'✓' if self.fahrplan_valid_xml else '✗'}")
        lines.append(f"  Has Events: {'✓' if self.fahrplan_has_events else '✗'}")
        if self.fahrplan_error:
            lines.append(f"  Error: {self.fahrplan_error}")

        # Podcast results
        lines.append("\n🎙️  Podcast Feed:")
        lines.append(f"  HTTP Status: {self.podcast_status or 'N/A'}")
        lines.append(f"  Valid XML: {'✓' if self.podcast_valid_xml else '✗'}")
        lines.append(f"  Has Items: {'✓' if self.podcast_has_items else '✗'}")
        if self.podcast_error:
            lines.append(f"  Error: {self.podcast_error}")

        # Overall result
        lines.append(f"\n{'✅ PASS' if self.is_success else '❌ FAIL'}")

        return "\n".join(lines)


def validate_fahrplan_xml(content: str) -> tuple[bool, bool, Optional[str]]:
    """Validate fahrplan schedule XML structure and content.

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


def validate_event(event_id: str, event_config: dict) -> ValidationResult:
    """Validate a single event's URLs."""
    result = ValidationResult(event_id)

    # Validate Fahrplan URL
    fahrplan_url = event_config.get("fahrplan_url")
    if fahrplan_url:
        try:
            print(f"  Fetching {fahrplan_url}...", end=" ")
            response = requests.get(fahrplan_url, timeout=30)
            result.fahrplan_status = response.status_code

            if response.status_code == 200:
                print("✓")
                is_valid, has_events, error = validate_fahrplan_xml(response.text)
                result.fahrplan_valid_xml = is_valid
                result.fahrplan_has_events = has_events
                result.fahrplan_error = error
            else:
                print(f"✗ (HTTP {response.status_code})")
                result.fahrplan_error = f"HTTP {response.status_code}"

        except requests.RequestException as e:
            print(f"✗ ({str(e)})")
            result.fahrplan_error = str(e)

    # Validate Podcast URL
    podcast_url = event_config.get("media_feed_url")
    if podcast_url:
        try:
            print(f"  Fetching {podcast_url}...", end=" ")
            response = requests.get(podcast_url, timeout=30)
            result.podcast_status = response.status_code

            if response.status_code == 200:
                print("✓")
                is_valid, has_items, error = validate_podcast_xml(response.text)
                result.podcast_valid_xml = is_valid
                result.podcast_has_items = has_items
                result.podcast_error = error
            else:
                print(f"✗ (HTTP {response.status_code})")
                result.podcast_error = f"HTTP {response.status_code}"

        except requests.RequestException as e:
            print(f"✗ ({str(e)})")
            result.podcast_error = str(e)

    return result


def main():
    """Run validation for all events in config.yaml."""
    # Load config
    config_path = Path("config.yaml")
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    events = config.get("events", {})
    if not events:
        print("❌ No events found in config")
        sys.exit(1)

    print(f"🔍 Validating {len(events)} events...\n")

    # Validate each event
    results = []
    for event_id, event_config in sorted(events.items()):
        print(f"📡 {event_id} ({event_config.get('year', 'unknown')})")
        result = validate_event(event_id, event_config)
        results.append(result)

    # Print detailed results
    print("\n" + "=" * 70)
    print("DETAILED RESULTS")
    print("=" * 70)

    for result in results:
        print(result)

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in results if r.is_success)
    failed = len(results) - passed

    print(f"\nTotal Events: {len(results)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")

    if failed > 0:
        print("\n⚠️  Some validations failed. See details above.")
        sys.exit(1)
    else:
        print("\n🎉 All validations passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
