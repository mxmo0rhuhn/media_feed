#!/usr/bin/env python3
"""Media Feed CLI - All-in-one implementation."""

import base64
from email.utils import formatdate
from pathlib import Path
from typing import Any, Optional
from xml.dom import minidom

import click
import requests
import yaml
from jinja2 import Environment, FileSystemLoader

from media_feed.feedback import format_feedback_section


# --- Config Loading ---
def load_config() -> dict[str, Any]:
    """Load config.yaml."""
    with open("config.yaml") as f:
        return yaml.safe_load(f)


# --- Feedback Integration ---
def format_item_description(item: dict[str, Any]) -> str:
    """Format item description with feedback prepended."""
    feedback_section = format_feedback_section(item.get("feedback"))
    description = item.get("description", "")
    return feedback_section + description


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
        if not 1 <= rating <= 5:
            click.echo("⚠️  Invalid rating (must be 1-5). Skipping.", err=True)
            return None
    except ValueError:
        click.echo("⚠️  Invalid input. Skipping.", err=True)
        return None

    # Get comment
    comment = click.prompt(
        "Comment (optional, Enter to skip)", default="", show_default=False
    ).strip()

    # Create feedback entry
    feedback_entry = {"rating": rating}
    if username:
        feedback_entry["username"] = username
    if comment:
        feedback_entry["comment"] = comment

    return feedback_entry


# --- RSS Generation (replaces build script) ---
def build_feed(
    yaml_file: Path, output_dir: Path, config: dict[str, Any], include_all_ratings: bool = False
) -> Path:
    """Build RSS feed from YAML file.

    Args:
        yaml_file: Path to input YAML file
        output_dir: Directory for output RSS file
        config: Configuration dict
        include_all_ratings: If False, exclude talks with rating ≤2 (default: False)
    """
    from media_feed.feedback import calculate_average_rating

    # 1. Load YAML
    with yaml_file.open() as f:
        data = yaml.safe_load(f)

    # 2. Filter feed items by rating if needed
    if not include_all_ratings and "feed" in data:
        filtered_feed = []
        for item in data["feed"]:
            feedback = item.get("feedback", [])
            if feedback:
                avg_rating = calculate_average_rating(feedback)
                # Exclude if average rating is 2 or lower
                if avg_rating is not None and avg_rating <= 2.0:
                    continue
            # Include items with no ratings or ratings > 2
            filtered_feed.append(item)
        data["feed"] = filtered_feed

    # 3. Load Jinja2 template
    template_path = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(str(template_path)))
    template = env.get_template("rss_template.xml.j2")

    # 4. Render with current timestamp
    now = formatdate(timeval=None, localtime=False, usegmt=True)
    xml_content = template.render(
        data=data,
        global_config=config.get("global", {}),
        now=now,
        generator="media-feed Python CLI",
        format_item_description=format_item_description,
    )

    # 5. Write output
    output_file = output_dir / yaml_file.name.replace("media_", "feed_").replace(".yml", ".xml")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(xml_content, encoding="utf-8")

    return output_file


# --- CCC Search (replaces ccc_event.py) ---
def download_cached(url: str, cache_dir: Path) -> Path:
    """Download XML with caching."""
    cache_name = base64.b64encode(url.encode()).decode()
    cache_path = cache_dir / cache_name

    if not cache_path.exists():
        resp = requests.get(url, verify=True, timeout=30)
        resp.raise_for_status()
        cache_path.write_bytes(resp.content)

    return cache_path


def map_track_to_categories(track: str, config: dict[str, Any]) -> list[str]:
    """Map CCC track to Apple Podcast categories using global config mapping.

    The config format is: Apple category -> list of CCC tracks
    This function inverts it to find which Apple categories apply to a given CCC track.
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
    query: str, event_config: dict[str, Any], config: dict[str, Any], use_long_desc: bool = False
) -> Optional[dict[str, Any]]:
    """Search for CCC talk and return YAML entry dict."""
    cache_dir = Path("/tmp/media_feed_cache")
    cache_dir.mkdir(exist_ok=True)

    # Download XMLs
    fahrplan_file = download_cached(event_config["fahrplan_url"], cache_dir)
    media_file = download_cached(event_config["media_feed_url"], cache_dir)

    # Parse XMLs
    fahrplan_dom = minidom.parse(str(fahrplan_file))
    media_dom = minidom.parse(str(media_file))

    # Search logic (from ccc_event.py)
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
            track_elems[0].childNodes[0].data if track_elems and track_elems[0].childNodes else ""
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

            web_url = f"{event_config['event_pattern_head']}{event_id}{event_config['event_pattern_tail']}"

            final_desc = description if use_long_desc else media_desc

            # Map track to categories
            categories = map_track_to_categories(track, config)

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

    return None


# --- URL Validation ---
def validate_url(url: str, timeout: int = 10) -> tuple[bool, str]:
    """Validate URL with HEAD request."""
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            return True, "OK"
        else:
            return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)


# --- CLI Commands ---
@click.group()
@click.version_option(version="1.0.0")
def main() -> None:
    """Media Feed CLI - Generate RSS feeds for CCC media events."""
    pass


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
    config = load_config()
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
            output = build_feed(yaml_file, output_path, config, include_all_ratings=all_ratings)
            click.echo(f"✓ Built: {output}")
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
    config = load_config()

    # Resolve event
    if event:
        event_key = event
    elif year:
        # Find event by year
        event_key = None
        for key, evt in config["events"].items():
            if evt["year"] == year:
                event_key = key
                break
        if not event_key:
            click.echo(f"No event found for year {year}", err=True)
            return
    else:
        # Use latest event
        event_key = max(config["events"].keys(), key=lambda k: config["events"][k]["year"])

    event_config = config["events"][event_key]

    # Search
    entry = search_ccc_talk(query, event_config, config, long_desc)

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

    # Load existing YAML
    if output_file.exists():
        with output_file.open() as f:
            data = yaml.safe_load(f)
    else:
        click.echo(f"File not found: {output_file}", err=True)
        return

    # Insert at top of feed
    if "feed" not in data:
        data["feed"] = []
    data["feed"].insert(0, entry)

    # Write back
    with output_file.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    click.echo(f"\n✓ Added entry to {output_file}")


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
    if not congress_number:
        congress_number = year - 1984

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
    if validate:
        click.echo("\nValidating URLs...")
        for key in ["fahrplan_url", "media_feed_url"]:
            url = event_config[key]
            is_valid, msg = validate_url(url)
            status = "✓" if is_valid else "✗"
            click.echo(f"{status} {key}: {msg}")

    # Generate YAML snippet
    click.echo("\n--- Add to config.yaml ---")
    click.echo(f"{event_id}:")
    for key, value in event_config.items():
        click.echo(f"  {key}: {value}")


@main.command()
@click.argument("event_file", type=click.Path(exists=True))
def rate(event_file: str) -> None:
    """Interactively rate talks in an event YAML file."""
    yaml_file = Path(event_file)

    # Load YAML
    with yaml_file.open() as f:
        data = yaml.safe_load(f)

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

    # Write back to YAML
    with yaml_file.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Summary
    click.echo("\n" + "━" * 50)
    click.echo(f"\n✅ Rating complete!")
    click.echo(f"   Rated: {rated_count}")
    click.echo(f"   Skipped: {skipped_count}")
    click.echo(f"\n💾 Saved to: {yaml_file}\n")


@main.command("list-by-rating")
@click.option("--event", "-e", help="Filter by event file (e.g., media/media_36C3.yml)")
@click.option("--min-rating", "-m", type=float, help="Minimum average rating")
def list_by_rating(event: Optional[str], min_rating: Optional[float]) -> None:
    """List talks sorted by rating."""
    from media_feed.feedback import calculate_average_rating

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

        with yaml_file.open() as f:
            data = yaml.safe_load(f)

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
        click.echo(
            f"{rating_display:<8} {title:<50} {talk['event']:<8} {talk['num_ratings']:<10}"
        )

    click.echo("━" * 80)
    click.echo(f"\nTotal: {len(talks_with_ratings)} rated talk(s)\n")


if __name__ == "__main__":
    main()
