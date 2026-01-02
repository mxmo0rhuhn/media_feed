"""RSS feed generation."""

from email.utils import formatdate
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from media_feed.feedback import calculate_average_rating, format_feedback_section
from media_feed.security.sanitizer import validate_file_path
from media_feed.utils.files import atomic_write
from media_feed.utils.logger import get_logger
from media_feed.validation import validate_yaml_data

logger = get_logger(__name__)


def format_item_description(item: dict[str, Any]) -> str:
    """Format item description with feedback prepended.

    Args:
        item: Feed item dictionary

    Returns:
        Formatted description with feedback section
    """
    feedback_section = format_feedback_section(item.get("feedback"))
    description = item.get("description", "")
    return feedback_section + description


def filter_feed_by_rating(
    feed_items: list[dict[str, Any]],
    include_all_ratings: bool = False,
) -> list[dict[str, Any]]:
    """Filter feed items by rating.

    Args:
        feed_items: List of feed items
        include_all_ratings: If False, exclude talks with rating ≤2

    Returns:
        Filtered list of feed items
    """
    if include_all_ratings:
        return feed_items

    filtered_items = []

    for item in feed_items:
        feedback = item.get("feedback", [])

        if feedback:
            avg_rating = calculate_average_rating(feedback)
            # Exclude if average rating is 2 or lower
            if avg_rating is not None and avg_rating <= 2.0:
                logger.debug(
                    f"Excluding talk '{item.get('title', 'Untitled')}' "
                    f"with rating {avg_rating:.1f}"
                )
                continue

        # Include items with no ratings or ratings > 2
        filtered_items.append(item)

    excluded_count = len(feed_items) - len(filtered_items)
    if excluded_count > 0:
        logger.info(f"Excluded {excluded_count} talk(s) with low ratings (≤2)")

    return filtered_items


def generate_rss_feed(
    data: dict[str, Any],
    global_config: dict[str, Any],
    output_file: Path,
    include_all_ratings: bool = False,
    validate: bool = True,
) -> Path:
    """Generate RSS feed from YAML data.

    Args:
        data: YAML data dictionary
        global_config: Global configuration
        output_file: Path to output RSS file
        include_all_ratings: If False, exclude talks with rating ≤2
        validate: Perform validation before generation

    Returns:
        Path to generated RSS file

    Raises:
        ValueError: If validation fails
    """
    # Validate data if requested
    if validate:
        validation_result = validate_yaml_data(data, output_file)

        if validation_result.has_errors():
            error_msg = "; ".join(validation_result.errors)
            raise ValueError(f"Validation failed: {error_msg}")

    # Filter feed by rating
    if "feed" in data:
        data["feed"] = filter_feed_by_rating(data["feed"], include_all_ratings)

    # Load Jinja2 template
    template_dir = Path(__file__).parent.parent
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("rss_template.xml.j2")

    # Render with current timestamp
    now = formatdate(timeval=None, localtime=False, usegmt=True)
    xml_content = template.render(
        data=data,
        global_config=global_config,
        now=now,
        generator="media-feed Python CLI",
        format_item_description=format_item_description,
    )

    # Write atomically
    output_file.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(output_file, xml_content)

    logger.info(f"Generated RSS feed: {output_file}")
    return output_file
