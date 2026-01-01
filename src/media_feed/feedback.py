"""Feedback formatting and utilities."""

from typing import Any, Optional


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
