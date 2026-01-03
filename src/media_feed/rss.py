"""RSS feed generation with feedback formatting."""

from email.utils import formatdate
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader

from media_feed.utils.file_utils import atomic_write
from media_feed.utils.logger import get_logger
from media_feed.utils.yaml_utils import validate_yaml_data

logger = get_logger(__name__)


# Feedback formatting functions

def format_stars(rating: int) -> str:
    """Convert numeric rating to star display."""
    if not 1 <= rating <= 5:
        return ""
    return "⭐" * rating


def format_feedback_line(feedback_item: dict[str, Any]) -> str:
    """Format a single feedback entry for display.

    Examples:
        ⭐⭐⭐⭐⭐ (5/5) - max: Must see talk!
        ⭐⭐⭐⭐ (4/5) Good overview
        ⭐⭐⭐ (3/5) - anna
    """
    rating = feedback_item.get("rating")
    if rating is None:
        return ""

    stars = format_stars(rating)
    rating_text = f"{stars} ({rating}/5)"

    username = feedback_item.get("username", "").strip()
    comment = feedback_item.get("comment", "").strip()

    # Build the line based on what's present
    if username and comment:
        return f"{rating_text} - {username}: {comment}"
    elif username:
        return f"{rating_text} - {username}"
    elif comment:
        return f"{rating_text} {comment}"
    else:
        return rating_text


def calculate_average_rating(feedback_list: list[dict[str, Any]]) -> Optional[float]:
    """Calculate average rating from feedback list."""
    ratings = [f.get("rating") for f in feedback_list if f.get("rating") is not None]
    if not ratings:
        return None
    return sum(ratings) / len(ratings)


def format_feedback_section(feedback_list: Optional[list[dict[str, Any]]]) -> str:
    """Format complete feedback section for RSS description.

    Returns empty string if no feedback, otherwise returns formatted block:

    ━━━━━━━━━━━━━━━━━━━━━━━━━━
    📊 RATINGS (Average: 4.5/5 from 2 ratings)

    ⭐⭐⭐⭐⭐ (5/5) - max: Must see!
    ⭐⭐⭐⭐ (4/5) Good overview

    ━━━━━━━━━━━━━━━━━━━━━━━━━━

    """
    if not feedback_list:
        return ""

    # Filter out invalid entries
    valid_feedback = [f for f in feedback_list if f.get("rating") is not None]
    if not valid_feedback:
        return ""

    avg_rating = calculate_average_rating(valid_feedback)
    num_ratings = len(valid_feedback)

    lines = []
    lines.append("━" * 30)
    lines.append(f"📊 RATINGS (Average: {avg_rating:.1f}/5 from {num_ratings} rating{'s' if num_ratings != 1 else ''})")
    lines.append("")

    for feedback_item in valid_feedback:
        line = format_feedback_line(feedback_item)
        if line:
            lines.append(line)

    lines.append("")
    lines.append("━" * 30)
    lines.append("")

    return "\n".join(lines)


# RSS generation functions

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
    template_dir = Path(__file__).parent
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
