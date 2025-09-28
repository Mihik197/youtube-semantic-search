# src/services/duration_utils.py
"""Helpers for working with ISO 8601 durations returned by the YouTube API."""

from __future__ import annotations

import re
from typing import Optional


_ISO_DURATION_RE = re.compile(
    r"^P"
    r"(?:(?P<days>\d+)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?"
    r")?$"
)


def parse_iso8601_duration(value: str | None) -> Optional[int]:
    """Return the duration in seconds or ``None`` when parsing fails."""

    if not value or not isinstance(value, str):
        return None

    match = _ISO_DURATION_RE.fullmatch(value.strip().upper())
    if not match:
        return None

    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return seconds + minutes * 60 + hours * 3600 + days * 86400


def format_watch_time(total_seconds: Optional[int]) -> str:
    """Express ``total_seconds`` as a compact string (e.g. ``'2h 15m'``)."""

    if total_seconds is None:
        return ""

    if total_seconds < 60:
        return f"{total_seconds}s"

    minutes, seconds = divmod(total_seconds, 60)
    if total_seconds < 3600:
        return f"{minutes}m"

    hours, minutes = divmod(minutes, 60)
    if total_seconds < 86400:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"

    days, hours = divmod(hours, 24)
    text = f"{days}d"
    if hours:
        text += f" {hours}h"
    return text

__all__ = [
    'parse_iso8601_duration',
    'format_watch_time'
]
