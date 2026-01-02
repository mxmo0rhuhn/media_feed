"""Secure XML parsing utilities to prevent XXE attacks."""

from pathlib import Path
from typing import Any
from xml.dom.minidom import Document

try:
    from defusedxml import minidom
except ImportError:
    # Fallback with warnings if defusedxml not available
    import warnings
    from xml.dom import minidom

    warnings.warn(
        "defusedxml not installed. XML parsing may be vulnerable to XXE attacks. "
        "Install with: pip install defusedxml",
        category=SecurityWarning,
        stacklevel=2,
    )


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
