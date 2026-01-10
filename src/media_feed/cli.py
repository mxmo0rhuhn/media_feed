"""Media Feed CLI command implementations."""

import logging
import re
from pathlib import Path
from typing import Any, Optional

import click

from media_feed.ccc_api import search_ccc_talk
from media_feed.config import (
    ConfigError,
    calculate_congress_number,
    get_event_by_year,
    get_latest_event,
    load_config,
)
from media_feed.rss import calculate_average_rating, generate_rss_feed
from media_feed.utils.http_utils import check_url_exists
from media_feed.utils.logger import configure_logging
from media_feed.utils.validation_utils import validate_event_urls
from media_feed.utils.yaml_utils import load_yaml, save_yaml, validate_yaml_data

# Input sanitization constants
MAX_USERNAME_LENGTH = 50
MAX_COMMENT_LENGTH = 500


def _initialize_media_file(event_id: str, year: int, congress_number: int) -> None:
    """Initialize media YAML file for a new event.

    Args:
        event_id: Event ID (e.g., '37c3')
        year: Event year
        congress_number: Congress number

    Raises:
        Exception: If file creation fails
    """
    # Create media directory if it doesn't exist
    media_dir = Path("media")
    media_dir.mkdir(exist_ok=True)

    # Generate filename with lowercase event_id
    media_file = media_dir / f"media_{event_id}.yml"

    # Check if file already exists
    if media_file.exists():
        click.echo(f"✓ Media file already exists: {media_file}")
        return

    # Try to find event logo (PNG format for Apple Podcasts compatibility)
    logo_url = f"https://static.media.ccc.de/media/congress/{year}/logo.png"

    # Check if logo exists
    if not check_url_exists(logo_url):
        click.echo(
            f"⚠️  Warning: Event logo not found at {logo_url}",
            err=True,
        )
        click.echo(
            "  Note: Apple Podcasts requires PNG/JPG format (SVG not supported)",
            err=True,
        )
        logo_url = ""  # Leave empty if not found

    # Create media file content
    event_name = event_id.upper()
    meta: dict[str, str] = {
        "title": f"{event_name} media feed",
        "description": (
            f"A curated feed for different talks of the {event_name} "
            f"(Chaos Communication Congress {year})."
        ),
    }
    # Add image_url only if logo was found
    if logo_url:
        meta["image_url"] = logo_url

    media_data: dict[str, Any] = {
        "meta": meta,
        "feed": [],
    }

    # Save the file
    save_yaml(media_file, media_data)
    click.echo(f"✓ Created media file: {media_file}")

    if not logo_url:
        click.echo(f"  You can manually add image_url to {media_file} when available")


def sanitize_username(username: str, max_length: int = MAX_USERNAME_LENGTH) -> str:
    """Sanitize username input.

    Args:
        username: Raw username input
        max_length: Maximum allowed length

    Returns:
        Sanitized username

    Raises:
        ValueError: If username is invalid
    """
    if not username:
        raise ValueError("Username cannot be empty")

    # Remove control characters and limit length
    sanitized = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", username)
    sanitized = sanitized.strip()[:max_length]

    if not sanitized:
        raise ValueError("Username contains only invalid characters")

    return sanitized


def sanitize_comment(comment: str, max_length: int = MAX_COMMENT_LENGTH) -> str:
    """Sanitize comment input.

    Args:
        comment: Raw comment input
        max_length: Maximum allowed length

    Returns:
        Sanitized comment
    """
    if not comment:
        return ""

    # Remove control characters except newlines and tabs
    sanitized = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]", "", comment)
    sanitized = sanitized.strip()[:max_length]

    return sanitized


def validate_rating(rating: int) -> int:
    """Validate rating value.

    Args:
        rating: Rating value to validate

    Returns:
        Validated rating

    Raises:
        ValueError: If rating is out of range
    """
    if not isinstance(rating, int) or not 1 <= rating <= 5:
        raise ValueError("Rating must be an integer between 1 and 5")
    return rating


def prompt_for_feedback(username: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Prompt user for a single rating and comment.

    Returns feedback dict or None if skipped.
    """
    # Get rating
    rating_input = click.prompt(
        "Rate this talk (1-5, Enter to skip)",
        default="",
        show_default=False,
    ).strip()

    # Skip if empty
    if not rating_input:
        return None

    # Validate rating
    try:
        rating = int(rating_input)
        rating = validate_rating(rating)
    except (ValueError, TypeError):
        click.echo("⚠️  Invalid rating (must be 1-5). Skipping.", err=True)
        return None

    # Get comment
    comment_raw = click.prompt(
        "Comment (optional, Enter to skip)", default="", show_default=False
    ).strip()

    # Create feedback entry
    feedback_entry: dict[str, int | str] = {"rating": rating}

    if username:
        try:
            sanitized_username = sanitize_username(username)
            feedback_entry["username"] = sanitized_username
        except ValueError as e:
            click.echo(f"⚠️  Invalid username: {e}", err=True)

    if comment_raw:
        sanitized_comment = sanitize_comment(comment_raw)
        if sanitized_comment:
            feedback_entry["comment"] = sanitized_comment

    return feedback_entry


# CLI Commands


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version="1.0.0")
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Increase verbosity (-v: WARNING+, -vv: INFO+, -vvv: DEBUG+)",
)
def main(verbose: int) -> None:
    """Media Feed CLI - Generate RSS feeds for CCC media events."""
    # Map verbosity count to log levels
    if verbose >= 3:
        configure_logging(logging.DEBUG)  # -vvv: DEBUG and above
    elif verbose == 2:
        configure_logging(logging.INFO)  # -vv: INFO and above
    elif verbose == 1:
        configure_logging(logging.WARNING)  # -v: WARNING and above
    else:
        configure_logging(logging.ERROR)  # Default: ERROR only


@main.command()
@click.argument("input_files", nargs=-1, type=click.Path(exists=True))
@click.option("--all", "-a", is_flag=True, help="Build all media YAML files")
@click.option("--output-dir", "-o", default="feeds", help="Output directory")
@click.option(
    "--all-ratings",
    is_flag=True,
    help="Include talks with all ratings (default: exclude talks rated ≤2)",
)
def build(input_files: tuple[str, ...], all: bool, output_dir: str, all_ratings: bool) -> None:
    """Generate RSS feeds from YAML files.

    By default, talks with an average rating of 2 or lower are excluded from the RSS feed.
    Use --all-ratings to include all talks regardless of rating.
    """
    try:
        config = load_config()
    except (ConfigError, FileNotFoundError) as e:
        click.echo(f"✗ Configuration error: {e}", err=True)
        return

    output_path = Path(output_dir)

    # Determine files to build
    if all:
        media_dir = Path("media")
        files_to_process = list(media_dir.glob("media_*.yml"))
    else:
        files_to_process = [Path(f) for f in input_files]

    if not files_to_process:
        click.echo("No files to build. Use --all or specify files.", err=True)
        return

    for yaml_file in files_to_process:
        try:
            # Load YAML data
            data = load_yaml(yaml_file)

            # Validate and show warnings/errors
            validation_result = validate_yaml_data(data, yaml_file)

            if validation_result.has_warnings():
                click.echo(f"\n⚠️  Warnings for {yaml_file.name}:", err=True)
                for warning in validation_result.warnings:
                    click.echo(f"   • {warning}", err=True)

            if validation_result.has_errors():
                click.echo(f"\n❌ Errors for {yaml_file.name}:", err=True)
                for error in validation_result.errors:
                    click.echo(f"   • {error}", err=True)
                click.echo(f"✗ Failed {yaml_file}: Validation failed", err=True)
                continue

            # Generate RSS feed
            output_file = output_path / yaml_file.name.replace("media_", "feed_").replace(
                ".yml", ".xml"
            )

            output_path_result, was_written = generate_rss_feed(
                data=data,
                global_config=config.get("global", {}),
                output_file=output_file,
                include_all_ratings=all_ratings,
                validate=False,  # Already validated above
            )

            if was_written:
                click.echo(f"✓ Built: {output_file}")
            else:
                click.echo(f"○ Unchanged: {output_file}")

        except Exception as e:
            click.echo(f"✗ Failed {yaml_file}: {e}", err=True)


@main.command()
@click.argument("query")
@click.option("--event", "-e", help="Event name (e.g., 36c3)")
@click.option("--year", "-y", type=int, help="Year of the event")
@click.option("--output", "-o", help="Output YAML file")
@click.option("--long-desc", "-l", is_flag=True, help="Use long description from Fahrplan")
@click.option(
    "--categories",
    "-c",
    help="Override category (if multiple provided, only first is used)",
)
def add(
    query: str,
    event: Optional[str],
    year: Optional[int],
    output: Optional[str],
    long_desc: bool,
    categories: Optional[str],
) -> None:
    """Search CCC events and add media items to YAML."""
    try:
        config = load_config()
    except (ConfigError, FileNotFoundError) as e:
        click.echo(f"✗ Configuration error: {e}", err=True)
        return

    # Resolve event
    if event:
        event_key = event
        if event_key not in config["events"]:
            click.echo(f"✗ Event '{event}' not found in configuration", err=True)
            return
        event_config = config["events"][event_key]
    elif year:
        result = get_event_by_year(config, year)
        if not result:
            click.echo(f"✗ No event found for year {year}", err=True)
            return
        event_key, event_config = result
    else:
        try:
            event_key, event_config = get_latest_event(config)
        except ConfigError as e:
            click.echo(f"✗ {e}", err=True)
            return

    # Search
    try:
        entry = search_ccc_talk(query, event_config, config, long_desc, event_key)
    except Exception as e:
        click.echo(f"✗ Search failed: {e}", err=True)
        return

    if not entry:
        congress_num = event_config.get("congress_number", "?")
        year = event_config.get("year", "?")
        click.echo(
            f"✗ No matching talk found for '{query}' in {event_key.upper()} "
            f"(Congress #{congress_num}, {year})",
            err=True,
        )
        click.echo(
            f"  Tip: Try a shorter or more specific search term, or check the event's "
            f"schedule at {event_config.get('fahrplan_url', 'N/A')}",
            err=True,
        )
        return

    # Override category if provided
    if categories:
        # Take first category from comma-separated list
        category_list = [cat.strip() for cat in categories.split(",")]
        entry["category"] = category_list[0]

    click.echo("\n✓ Found talk:")
    click.echo(f"  Title: {entry['title']}")
    click.echo(f"  Speakers: {entry['speakers']}")
    click.echo(f"  Category: {entry.get('category', 'N/A')}")

    # Prompt for feedback
    click.echo("\n" + ("━" * 50))
    if click.confirm("Would you like to rate this talk?", default=True):
        username = click.prompt(
            "Username (optional, press Enter to skip)", default="", show_default=False
        ).strip()

        feedback = prompt_for_feedback(username if username else None)
        if feedback:
            entry["feedback"] = [feedback]
            click.echo("✓ Rating saved")

    # Determine output file
    output_file = Path(output) if output else Path(f"media/media_{event_key}.yml")

    try:
        # Load existing YAML
        if output_file.exists():
            data = load_yaml(output_file)
        else:
            click.echo(f"✗ File not found: {output_file}", err=True)
            return

        # Insert at top of feed
        if "feed" not in data:
            data["feed"] = []
        data["feed"].insert(0, entry)

        # Write back
        save_yaml(output_file, data)

        click.echo(f"\n✓ Added entry to {output_file}")

    except Exception as e:
        click.echo(f"✗ Failed to save: {e}", err=True)


@main.command("new-event")
@click.argument("year", type=int)
@click.option(
    "--congress-number",
    "-c",
    type=int,
    help="Congress number (auto-calculated if not provided)",
)
@click.option("--validate/--no-validate", default=True, help="Validate URLs")
@click.option(
    "--try-all-patterns",
    is_flag=True,
    help="Try all known URL patterns and suggest the working one",
)
def new_event(
    year: int, congress_number: Optional[int], validate: bool, try_all_patterns: bool
) -> None:
    """Create new CCC event configuration."""
    # Auto-calculate congress number if not provided
    if not congress_number:
        try:
            config = load_config()
            congress_number = calculate_congress_number(year, config)
            click.echo(
                f"Auto-calculated congress number: {congress_number} "
                "(based on most recent event in config)"
            )
        except (ConfigError, FileNotFoundError) as e:
            click.echo(f"Error calculating congress number: {e}", err=True)
            click.echo("Please provide congress number manually with -c option", err=True)
            return

    event_id = f"{congress_number}c3"

    # Generate URL patterns to try (from newest to oldest patterns)
    fahrplan_patterns = [
        # 39c3 pattern
        f"https://fahrplan.events.ccc.de/congress/{year}/fahrplan/schedules/schedule.xml",
        f"https://pretalx.c3voc.de/{event_id}/schedule/export/schedule.xml",  # 38c3 pattern
        f"https://fahrplan.events.ccc.de/congress/{year}/fahrplan/schedule.xml",  # 37c3 pattern
    ]

    # Podcast feed URL (consistent pattern)
    podcast_url = f"https://media.ccc.de/c/{event_id}/podcast/mp4-hq.xml"

    # Try all patterns when validating to find the one that works
    if validate:
        if try_all_patterns:
            click.echo("\n🔍 Trying all known URL patterns...\n")

        working_fahrplan = None

        for idx, fahrplan_url in enumerate(fahrplan_patterns, 1):
            pattern_names = [
                "39c3 pattern (schedules)",
                "38c3 pattern (pretalx)",
                "37c3 pattern (standard)",
            ]
            pattern_name = pattern_names[idx - 1]

            if try_all_patterns:
                click.echo(f"Pattern {idx} - {pattern_name}:")
                click.echo(f"  {fahrplan_url}")

            fahrplan_result, _ = validate_event_urls(fahrplan_url, podcast_url)

            if fahrplan_result.is_success:
                if try_all_patterns:
                    click.echo(
                        f"  ✓ Works! (HTTP {fahrplan_result.status_code}, valid XML, has events)\n"
                    )
                if not working_fahrplan:
                    working_fahrplan = fahrplan_url
                    if not try_all_patterns:
                        # Found a working pattern, stop trying
                        break
            else:
                if try_all_patterns:
                    error_msg = fahrplan_result.error or f"HTTP {fahrplan_result.status_code}"
                    click.echo(f"  ✗ Failed: {error_msg}\n")

        # Use the first working pattern or default to 39c3 pattern (newest)
        fahrplan_url = working_fahrplan or fahrplan_patterns[0]

        if try_all_patterns:
            if working_fahrplan:
                click.echo(f"✅ Selected working pattern: {fahrplan_url}\n")
            else:
                click.echo(f"⚠️  No patterns worked. Using default: {fahrplan_url}\n")
    else:
        # No validation, default to newest pattern (39c3)
        fahrplan_url = fahrplan_patterns[0]

    # Event patterns are now optional - URLs are extracted from <url> tag
    # Advanced users can manually edit config.yaml if they need custom patterns

    # Generate config (without event_pattern_* since URLs are extracted from XML)
    event_config = {
        "year": year,
        "congress_number": congress_number,
        "fahrplan_url": fahrplan_url,
        "media_feed_url": podcast_url,
    }

    # Validate if requested (and not already done with --try-all-patterns)
    all_valid = True
    if validate and not try_all_patterns:
        click.echo("\nValidating URLs...")

        fahrplan_result, podcast_result = validate_event_urls(
            str(event_config["fahrplan_url"]), str(event_config["media_feed_url"])
        )

        # Display fahrplan validation
        if fahrplan_result.is_success:
            click.echo(
                f"✓ fahrplan_url: OK (HTTP {fahrplan_result.status_code}, valid XML, has events)"
            )
        else:
            error_msg = fahrplan_result.error or f"HTTP {fahrplan_result.status_code}"
            click.echo(f"✗ fahrplan_url: {error_msg}")
            if fahrplan_result.status_code == 200 and not fahrplan_result.has_content:
                click.echo(f"  Note: XML is valid but {fahrplan_result.error}")
            all_valid = False

        # Display podcast validation
        if podcast_result.is_success:
            click.echo(
                f"✓ media_feed_url: OK (HTTP {podcast_result.status_code}, valid RSS, has items)"
            )
        else:
            error_msg = podcast_result.error or f"HTTP {podcast_result.status_code}"
            click.echo(f"✗ media_feed_url: {error_msg}")
            if podcast_result.status_code == 200 and not podcast_result.has_content:
                click.echo(f"  Note: XML is valid but {podcast_result.error}")
            all_valid = False
    elif validate and try_all_patterns:
        # Already validated, just check the final podcast URL
        click.echo("Validating podcast URL...")
        _, podcast_result = validate_event_urls(fahrplan_url, podcast_url)
        if podcast_result.is_success:
            click.echo(
                f"✓ media_feed_url: OK (HTTP {podcast_result.status_code}, valid RSS, has items)"
            )
        else:
            error_msg = podcast_result.error or f"HTTP {podcast_result.status_code}"
            click.echo(f"✗ media_feed_url: {error_msg}")
            all_valid = False

    # Auto-add to config if validation passed or was not requested
    if not validate or all_valid:
        try:
            # Load existing config
            config_path = Path("config.yaml")
            if config_path.exists():
                config = load_yaml(config_path)
            else:
                config = {"global": {}, "events": {}}

            # Check if event already exists
            if event_id in config.get("events", {}):
                click.echo(
                    f"\n⚠ Event '{event_id}' already exists in config.yaml",
                    err=True,
                )
                click.echo(
                    "Event was not added. Remove the existing entry first "
                    "if you want to replace it."
                )
                return

            # Add new event
            if "events" not in config:
                config["events"] = {}
            config["events"][event_id] = event_config

            # Save updated config
            save_yaml(config_path, config)
            click.echo(f"\n✓ Event '{event_id}' added to config.yaml successfully!")

            # Initialize media YAML file
            try:
                _initialize_media_file(event_id, year, congress_number)
            except Exception as e:
                click.echo(
                    f"\n⚠️  Warning: Failed to initialize media file: {e}",
                    err=True,
                )
                click.echo(f"You can manually create media/media_{event_id}.yml later.")

        except Exception as e:
            click.echo(f"\n✗ Error adding event to config.yaml: {e}", err=True)
            click.echo("\nYou can manually add the following to config.yaml:")
            click.echo(f"{event_id}:")
            for key, value in event_config.items():
                click.echo(f"  {key}: {value}")
    else:
        click.echo("\n✗ Validation failed. Event not added to config.yaml")
        click.echo("\nYou can manually add the following to config.yaml:")
        click.echo(f"{event_id}:")
        for key, value in event_config.items():
            click.echo(f"  {key}: {value}")


@main.command()
@click.argument("event_file", type=click.Path(exists=True))
def rate(event_file: str) -> None:
    """Interactively rate talks in an event YAML file."""
    yaml_file = Path(event_file)

    try:
        # Load YAML
        data = load_yaml(yaml_file)
    except Exception as e:
        click.echo(f"✗ Failed to load file: {e}", err=True)
        return

    if "feed" not in data or not data["feed"]:
        click.echo("No feed items found in the file.", err=True)
        return

    # Ask for username once at startup
    click.echo("\n📝 Interactive Rating Mode")
    click.echo("━" * 50)
    username = click.prompt(
        "Username (optional, press Enter to skip)", default="", show_default=False
    ).strip()

    if username:
        click.echo(f"\nRating as: {username}\n")
    else:
        click.echo("\nRating anonymously\n")

    total_talks = len(data["feed"])
    rated_count = 0
    skipped_count = 0

    # Iterate through each talk
    for idx, item in enumerate(data["feed"], start=1):
        click.echo("━" * 50)
        click.echo(f"\n🎬 {item.get('title', 'Untitled')} ({idx}/{total_talks})")

        speakers = item.get("speakers", "")
        if speakers:
            click.echo(f"   Speakers: {speakers}")

        # Prompt for feedback
        click.echo()
        feedback = prompt_for_feedback(username if username else None)

        if feedback:
            # Add to item
            if "feedback" not in item:
                item["feedback"] = []
            item["feedback"].append(feedback)
            click.echo("✓ Saved")
            rated_count += 1
        else:
            click.echo("⏭️  Skipped")
            skipped_count += 1

    try:
        # Write back to YAML
        save_yaml(yaml_file, data)

        # Summary
        click.echo("\n" + "━" * 50)
        click.echo("\n✅ Rating complete!")
        click.echo(f"   Rated: {rated_count}")
        click.echo(f"   Skipped: {skipped_count}")
        click.echo(f"\n💾 Saved to: {yaml_file}\n")

    except Exception as e:
        click.echo(f"\n✗ Failed to save: {e}", err=True)


@main.command("list-by-rating")
@click.option("--event", "-e", help="Filter by event (e.g., '39C3' or 'media/media_36C3.yml')")
@click.option("--min-rating", "-m", type=float, help="Minimum average rating")
@click.option("--category", "-c", help="Filter by category (e.g., 'Technology', 'Science')")
def list_by_rating(
    event: Optional[str], min_rating: Optional[float], category: Optional[str]
) -> None:
    """List talks sorted by rating."""
    # Determine files to process
    if event:
        # If event contains path separator or ends with .yml, treat as file path
        # Otherwise, treat as event name and construct path
        if "/" in event or event.endswith(".yml"):
            files_to_process = [Path(event)]
        else:
            # Convert event name to file path (e.g., "39C3" -> "media/media_39c3.yml")
            event_lower = event.lower()
            files_to_process = [Path(f"media/media_{event_lower}.yml")]
    else:
        media_dir = Path("media")
        files_to_process = list(media_dir.glob("media_*.yml"))

    if not files_to_process:
        click.echo("No files found.", err=True)
        return

    # Collect all talks with ratings
    talks_with_ratings = []

    for yaml_file in files_to_process:
        if not yaml_file.exists():
            continue

        try:
            data = load_yaml(yaml_file)
        except Exception as e:
            click.echo(f"⚠️  Failed to load {yaml_file}: {e}", err=True)
            continue

        event_name = yaml_file.stem.replace("media_", "").upper()

        for item in data.get("feed", []):
            feedback = item.get("feedback", [])
            if not feedback:
                continue

            avg_rating = calculate_average_rating(feedback)
            if avg_rating is None:
                continue

            # Apply min-rating filter
            if min_rating is not None and avg_rating < min_rating:
                continue

            # Apply category filter
            item_category = item.get("category", "")
            if category is not None and item_category.lower() != category.lower():
                continue

            talks_with_ratings.append(
                {
                    "title": item.get("title", "Untitled"),
                    "event": event_name,
                    "category": item_category,
                    "avg_rating": avg_rating,
                    "num_ratings": len([f for f in feedback if f.get("rating") is not None]),
                }
            )

    # Sort by rating (descending)
    talks_with_ratings.sort(key=lambda x: x["avg_rating"], reverse=True)

    # Display
    if not talks_with_ratings:
        click.echo("\nNo rated talks found.\n")
        return

    click.echo("\n" + "━" * 95)
    click.echo(f"{'Rating':<8} {'Title':<40} {'Category':<14} {'Event':<8} {'# Ratings':<10}")
    click.echo("━" * 95)

    for talk in talks_with_ratings:
        rating_display = f"{talk['avg_rating']:.1f}/5"
        title = talk["title"][:37] + "..." if len(talk["title"]) > 40 else talk["title"]
        cat = talk["category"][:11] + "..." if len(talk["category"]) > 14 else talk["category"]
        num = talk["num_ratings"]
        click.echo(f"{rating_display:<8} {title:<40} {cat:<14} {talk['event']:<8} {num:<10}")

    click.echo("━" * 95)
    click.echo(f"\nTotal: {len(talks_with_ratings)} rated talk(s)\n")


if __name__ == "__main__":
    main()
