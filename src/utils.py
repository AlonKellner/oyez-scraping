"""Utility functions for the Oyez scraper.

This module provides utility functions for the Oyez Supreme Court oral arguments scraper.
"""

from datetime import datetime


def parse_date(date_val: str | int | float | None) -> datetime:
    """Parse a date value from various formats.

    Args:
        date_val: Date value to parse, could be timestamp or string

    Returns
    -------
        Parsed datetime object
    """
    try:
        if isinstance(date_val, int | float):
            return datetime.fromtimestamp(date_val)
        if not isinstance(date_val, str):
            return datetime.fromtimestamp(0)

        # Try parsing common date formats
        for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
            try:
                return datetime.strptime(date_val, fmt)
            except ValueError:
                continue
    except (ValueError, TypeError):
        pass

    return datetime.fromtimestamp(0)
