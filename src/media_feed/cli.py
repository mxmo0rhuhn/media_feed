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
from media_feed.utils.http_utils import validate_url
from media_feed.utils.logger import configure_logging
from media_feed.utils.yaml_utils import load_yaml, save_yaml, validate_yaml_data

# Input sanitization constants
MAX_USERNAME_LENGTH = 50
MAX_COMMENT_LENGTH = 500


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
    feedback_entry = {"rating": rating}

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


@click.group()
@click.version_option(version="1.0.0")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--debug", "-d", is_flag=True, help="Enable debug logging")
def main(verbose: bool, debug: bool) -> None:
    """Media Feed CLI - Generate RSS feeds for CCC media events."""
    if debug:
        configure_logging(logging.DEBUG)
    elif verbose:
        configure_logging(logging.INFO)
    else:
        configure_logging(logging.WARNING)


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

            generate_rss_feed(
                data=data,
                global_config=config.get("global", {}),
                output_file=output_file,
                include_all_ratings=all_ratings,
                validate=False,  # Already validated above
            )

            click.echo(f"✓ Built: {output_file}")

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
    help="Override Apple Podcast categories (comma-separated, e.g., 'Technology,Science')",
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
        entry = search_ccc_talk(query, event_config, config, long_desc)
    except Exception as e:
        click.echo(f"✗ Search failed: {e}", err=True)
        return

    if not entry:
        click.echo("✗ No matching talk found", err=True)
        return

    # Override categories if provided
    if categories:
        entry["categories"] = [cat.strip() for cat in categories.split(",")]

    click.echo(f"\n✓ Found talk:")
    click.echo(f"  Title: {entry['title']}")
    click.echo(f"  Speakers: {entry['speakers']}")
    click.echo(f"  Categories: {', '.join(entry.get('categories', []))}")

    # Prompt for feedback
    click.echo("\n" + "━" * 50)
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
def new_event(year: int, congress_number: Optional[int], validate: bool) -> None:
    """Create new CCC event configuration."""
    # Auto-calculate congress number if not provided
    if not congress_number:
        try:
            config = load_config()
            congress_number = calculate_congress_number(year, config)
            click.echo(
                f"Auto-calculated congress number: {congress_number} (based on most recent event in config)"
            )
        except (ConfigError, FileNotFoundError) as e:
            click.echo(f"Error calculating congress number: {e}", err=True)
            click.echo("Please provide congress number manually with -c option", err=True)
            return

    event_id = f"{congress_number}c3"

    # Generate config
    event_config = {
        "year": year,
        "congress_number": congress_number,
        "fahrplan_url": f"https://fahrplan.events.ccc.de/congress/{year}/Fahrplan/schedule.xml",
        "media_feed_url": f"https://media.ccc.de/c/{event_id}/podcast/mp4.xml",
        "event_pattern_head": f"https://fahrplan.events.ccc.de/congress/{year}/Fahrplan/events/",
        "event_pattern_tail": ".html",
    }

    # Validate if requested
    all_valid = True
    if validate:
        click.echo("\nValidating URLs...")
        for key in ["fahrplan_url", "media_feed_url"]:
            url = event_config[key]
            is_valid, msg = validate_url(url)
            status = "✓" if is_valid else "✗"
            click.echo(f"{status} {key}: {msg}")
            if not is_valid:
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
                click.echo(f"\n⚠ Event '{event_id}' already exists in config.yaml", err=True)
                click.echo("Event was not added. Remove the existing entry first if you want to replace it.")
                return

            # Add new event
            if "events" not in config:
                config["events"] = {}
            config["events"][event_id] = event_config

            # Save updated config
            save_yaml(config_path, config)
            click.echo(f"\n✓ Event '{event_id}' added to config.yaml successfully!")

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
        click.echo(f"\n✅ Rating complete!")
        click.echo(f"   Rated: {rated_count}")
        click.echo(f"   Skipped: {skipped_count}")
        click.echo(f"\n💾 Saved to: {yaml_file}\n")

    except Exception as e:
        click.echo(f"\n✗ Failed to save: {e}", err=True)


@main.command("list-by-rating")
@click.option("--event", "-e", help="Filter by event file (e.g., media/media_36C3.yml)")
@click.option("--min-rating", "-m", type=float, help="Minimum average rating")
def list_by_rating(event: Optional[str], min_rating: Optional[float]) -> None:
    """List talks sorted by rating."""
    # Determine files to process
    if event:
        files_to_process = [Path(event)]
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

            talks_with_ratings.append(
                {
                    "title": item.get("title", "Untitled"),
                    "event": event_name,
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

    click.echo("\n" + "━" * 80)
    click.echo(f"{'Rating':<8} {'Title':<50} {'Event':<8} {'# Ratings':<10}")
    click.echo("━" * 80)

    for talk in talks_with_ratings:
        rating_display = f"{talk['avg_rating']:.1f}/5"
        title = talk["title"][:47] + "..." if len(talk["title"]) > 50 else talk["title"]
        click.echo(f"{rating_display:<8} {title:<50} {talk['event']:<8} {talk['num_ratings']:<10}")

    click.echo("━" * 80)
    click.echo(f"\nTotal: {len(talks_with_ratings)} rated talk(s)\n")


if __name__ == "__main__":
    main()
