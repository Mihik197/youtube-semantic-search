# src/services/duration_utils.py
"""Utilities for parsing and formatting YouTube ISO 8601 durations.

YouTube Data API v3 returns durations like:
  PT4M13S, PT1H2M5S, PT58S, PT2H, PT0S
according to ISO 8601 time designators.

We convert to integer seconds and provide human readable formatting for
watch-time aggregation.
"""
from __future__ import annotations
import re
from typing import Optional

# Precompile regex: PnYnMnDTnHnMnS but we only expect time component (no days) for video durations.
# However live streams or long videos may theoretically include days. Support D as well.
_ISO8601_DURATION_RE = re.compile(
    r'^P'                              # starts with P
    r'(?:(?P<days>\d+)D)?'            # days
    r'(?:T'                            # time part begins
    r'(?:(?P<hours>\d+)H)?'
    r'(?:(?P<minutes>\d+)M)?'
    r'(?:(?P<seconds>\d+)S)?'
    r')?$'
)

def parse_iso8601_duration(value: str | None) -> Optional[int]:
    """Parse YouTube ISO8601 duration string (e.g. 'PT1H2M5S') into seconds.

    Returns None if not parseable or value falsy.
    """
    if not value or not isinstance(value, str):
        return None
    value = value.strip().upper()
    if not value.startswith('P'):
        return None
    # YouTube always includes T when any time components present; handle edge forms gracefully.
    # Insert 'T' if we have only days (PnD) to allow regex to match; that's legitimate ISO but rare for videos.
    if 'T' not in value and not value.endswith('D'):
        # Cases like 'P0D' -> treat as zero seconds
        pass
    m = _ISO8601_DURATION_RE.match(value)
    if not m:
        return None
    days = int(m.group('days') or 0)
    hours = int(m.group('hours') or 0)
    minutes = int(m.group('minutes') or 0)
    seconds = int(m.group('seconds') or 0)
    total = seconds + minutes * 60 + hours * 3600 + days * 86400
    return total

def format_watch_time(total_seconds: int) -> str:
    """Return compact human readable string for channel total watch time.

    Rules:
      < 1 minute -> 'Xs'
      < 1 hour   -> 'Xm'
      < 1 day    -> 'Hh Mm' (omit minutes if 0)
      >= 1 day   -> 'Dd Hh' (omit hours if 0)
    """
    if total_seconds is None:
        return ''
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes = total_seconds // 60
    if total_seconds < 3600:
        return f"{minutes}m"
    hours = total_seconds // 3600
    minutes_remainder = (total_seconds % 3600) // 60
    if total_seconds < 86400:
        if minutes_remainder:
            return f"{hours}h {minutes_remainder}m"
        return f"{hours}h"
    days = total_seconds // 86400
    hours_remainder = (total_seconds % 86400) // 3600
    if hours_remainder:
        return f"{days}d {hours_remainder}h"
    return f"{days}d"

__all__ = [
    'parse_iso8601_duration',
    'format_watch_time'
]
