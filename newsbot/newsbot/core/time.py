"""Time and timezone utilities for RSS feed processing."""

import re
from datetime import datetime, timezone, timedelta
from typing import Optional
import email.utils

from newsbot.core.logging import get_logger

logger = get_logger(__name__)


def parse_feed_date(date_string: str) -> Optional[datetime]:
    """
    Parse date string from RSS/Atom feed into datetime object.
    
    Handles various date formats commonly found in feeds:
    - RFC 2822 (RSS)
    - ISO 8601 (Atom)
    - Various non-standard formats
    """
    if not date_string:
        return None
    
    date_string = date_string.strip()
    
    try:
        # Try RFC 2822 format first (common in RSS)
        dt = email.utils.parsedate_to_datetime(date_string)
        return dt
    except (ValueError, TypeError):
        pass
    
    # Common date format patterns
    patterns = [
        # ISO 8601 variants
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)',
        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)',
        
        # Alternative formats
        r'(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})',
        r'(\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2})',
        
        # Date only
        r'(\d{4}-\d{2}-\d{2})',
        r'(\d{2}/\d{2}/\d{4})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, date_string)
        if match:
            date_part = match.group(1)
            dt = _try_parse_formats(date_part)
            if dt:
                return dt
    
    logger.warning(f"Could not parse date: {date_string}")
    return None


def _try_parse_formats(date_string: str) -> Optional[datetime]:
    """Try various datetime formats."""
    formats = [
        # ISO 8601 with timezone
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S.%f%z',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S.%fZ',
        
        # ISO 8601 without timezone
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
        
        # Space separated
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M:%S.%f',
        
        # Alternative formats
        '%m/%d/%Y %H:%M:%S',
        '%d-%m-%Y %H:%M:%S',
        
        # Date only
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%d/%m/%Y',
    ]
    
    for fmt in formats:
        try:
            # Handle Z timezone
            if date_string.endswith('Z'):
                date_string = date_string[:-1] + '+00:00'
            
            dt = datetime.strptime(date_string, fmt)
            
            # If no timezone info, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            
            return dt
        except ValueError:
            continue
    
    return None


def normalize_timezone(dt: datetime, target_tz: timezone = timezone.utc) -> datetime:
    """
    Normalize datetime to target timezone.
    
    Args:
        dt: Input datetime
        target_tz: Target timezone (default UTC)
    
    Returns:
        Datetime in target timezone
    """
    if dt.tzinfo is None:
        # Assume UTC if no timezone
        dt = dt.replace(tzinfo=timezone.utc)
    
    return dt.astimezone(target_tz)


def get_taiwan_timezone() -> timezone:
    """Get Taiwan timezone (UTC+8)."""
    return timezone(timedelta(hours=8))


def to_taiwan_time(dt: datetime) -> datetime:
    """Convert datetime to Taiwan timezone."""
    return normalize_timezone(dt, get_taiwan_timezone())


def format_feed_date(dt: datetime) -> str:
    """Format datetime for display in feeds."""
    return dt.strftime('%Y-%m-%d %H:%M:%S %Z')


def is_recent(dt: datetime, hours: int = 24) -> bool:
    """Check if datetime is within specified hours from now."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    
    # Normalize to UTC for comparison
    dt_utc = normalize_timezone(dt)
    
    return dt_utc >= cutoff


def get_age_hours(dt: datetime) -> float:
    """Get age of datetime in hours from now."""
    now = datetime.now(timezone.utc)
    dt_utc = normalize_timezone(dt)
    
    delta = now - dt_utc
    return delta.total_seconds() / 3600


def parse_relative_time(time_str: str) -> Optional[datetime]:
    """
    Parse relative time strings like "2 hours ago", "1 day ago".
    
    Returns datetime in UTC.
    """
    if not time_str:
        return None
    
    time_str = time_str.lower().strip()
    now = datetime.now(timezone.utc)
    
    # Patterns for relative time
    patterns = [
        (r'(\d+)\s*minute?s?\s*ago', lambda m: now - timedelta(minutes=int(m.group(1)))),
        (r'(\d+)\s*hour?s?\s*ago', lambda m: now - timedelta(hours=int(m.group(1)))),
        (r'(\d+)\s*day?s?\s*ago', lambda m: now - timedelta(days=int(m.group(1)))),
        (r'(\d+)\s*week?s?\s*ago', lambda m: now - timedelta(weeks=int(m.group(1)))),
        (r'yesterday', lambda m: now - timedelta(days=1)),
        (r'today', lambda m: now),
    ]
    
    for pattern, func in patterns:
        match = re.search(pattern, time_str)
        if match:
            try:
                return func(match)
            except (ValueError, AttributeError):
                continue
    
    return None


def get_current_taiwan_time() -> datetime:
    """Get current time in Taiwan timezone."""
    return datetime.now(get_taiwan_timezone())


def get_current_utc_time() -> datetime:
    """Get current time in UTC."""
    return datetime.now(timezone.utc)