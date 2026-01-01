#!/usr/bin/env python3
"""Media Feed CLI - All-in-one implementation."""

import base64
import shutil
from email.utils import formatdate
from pathlib import Path
from typing import Any, Optional
from xml.dom import minidom

import click
import requests
import yaml
from jinja2 import Environment, FileSystemLoader


# --- Config Loading ---
def load_config() -> dict[str, Any]:
    """Load config.yaml."""
    with open("config.yaml") as f:
        return yaml.safe_load(f)


# --- RSS Generation (replaces build script) ---
def build_feed(yaml_file: Path, output_dir: Path, config: dict[str, Any]) -> Path:
    """Build RSS feed from YAML file."""
    # 1. Load YAML
    with yaml_file.open() as f:
        data = yaml.safe_load(f)

    # 2. Load Jinja2 template
    template_path = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(str(template_path)))
    template = env.get_template("rss_template.xml.j2")

    # 3. Render with current timestamp
    now = formatdate(timeval=None, localtime=False, usegmt=True)
    xml_content = template.render(data=data, now=now, generator="media-feed Python CLI")

    # 4. Write output
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
        resp = requests.get(url, stream=True, verify=True, timeout=30)
        resp.raise_for_status()
        with cache_path.open("wb") as f:
            shutil.copyfileobj(resp.raw, f)

    return cache_path


def search_ccc_talk(
    query: str, event_config: dict[str, Any], use_long_desc: bool = False
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
def build(input_files: tuple[str, ...], all: bool, output_dir: str) -> None:
    """Generate RSS feeds from YAML files."""
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
            output = build_feed(yaml_file, output_path, config)
            click.echo(f"✓ Built: {output}")
        except Exception as e:
            click.echo(f"✗ Failed {yaml_file}: {e}", err=True)


@main.command()
@click.argument("query")
@click.option("--event", "-e", help="Event name (e.g., 36c3)")
@click.option("--year", "-y", type=int, help="Year of the event")
@click.option("--output", "-o", help="Output YAML file")
@click.option("--long-desc", "-l", is_flag=True, help="Use long description from Fahrplan")
def add(
    query: str, event: Optional[str], year: Optional[int], output: Optional[str], long_desc: bool
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
    entry = search_ccc_talk(query, event_config, long_desc)

    if not entry:
        click.echo("✗ No matching talk found", err=True)
        return

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
    click.echo(f"\nTitle: {entry['title']}")
    click.echo(f"Speakers: {entry['speakers']}")


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


if __name__ == "__main__":
    main()
