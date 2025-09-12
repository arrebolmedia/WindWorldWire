"""RSS feed entry normalization helpers.

This module provides utilities to normalize raw RSS/Atom feed entries
into a consistent format for storage and processing.
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from bs4 import BeautifulSoup, NavigableString
from dateutil import parser as date_parser
import pytz

from newsbot.core.simhash import SimHash
from newsbot.core.logging import get_logger

logger = get_logger(__name__)


def clean_text(html_or_text: str) -> str:
    """
    Clean HTML/text content by stripping script/style tags, handling entities, and normalizing whitespace.
    
    Args:
        html_or_text: Raw HTML or text content
        
    Returns:
        Cleaned text with normalized whitespace
    """
    if not html_or_text:
        return ""
    
    try:
        # Parse with BeautifulSoup to handle HTML properly
        soup = BeautifulSoup(html_or_text, 'html.parser')
        
        # Remove script and style elements completely
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extract text content (automatically handles HTML entities)
        text = soup.get_text()
        
        # Normalize whitespace: collapse multiple spaces, tabs, newlines into single spaces
        text = re.sub(r'\s+', ' ', text.strip())
        
        return text
        
    except Exception as e:
        logger.warning(f"Error cleaning text: {e}", extra={"text_length": len(html_or_text)})
        # Fallback: basic HTML tag removal and entity decoding
        import html
        text = re.sub(r'<script[^>]*>.*?</script>', '', html_or_text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<[^>]+>', '', text)
        text = html.unescape(text)  # Decode HTML entities
        text = re.sub(r'\s+', ' ', text.strip())
        return text
        text = re.sub(r'\s+', ' ', text.strip())
        return text


def parse_datetime_guess(value) -> datetime:
    """
    Parse datetime from various formats with fallback to current UTC.
    
    Args:
        value: String, datetime, or other value to parse
        
    Returns:
        Parsed datetime object, defaults to current UTC time if parsing fails
    """
    def now_utc() -> datetime:
        """Get current UTC datetime."""
        return datetime.now(timezone.utc)
    
    if not value:
        return now_utc()
    
    # If already a datetime object
    if isinstance(value, datetime):
        # Ensure it's UTC
        return to_utc(value)
    
    # Try to parse string
    if isinstance(value, str):
        try:
            # Use dateutil parser for flexible parsing
            dt = date_parser.parse(value)
            return to_utc(dt)
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse datetime '{value}': {e}")
    
    # Fallback to current UTC time
    return now_utc()


def to_utc(dt: datetime) -> datetime:
    """
    Convert datetime to UTC timezone.
    
    Args:
        dt: Datetime object (may be naive or timezone-aware)
        
    Returns:
        UTC datetime object
    """
    if not dt:
        return datetime.now(timezone.utc)
    
    # If naive datetime, assume it's UTC
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    
    # Convert to UTC if timezone-aware
    return dt.astimezone(timezone.utc)


def detect_lang(title: str, summary: str, fallback_lang: str = 'en') -> str:
    """
    Detect language from title and summary text, with fallback to source language.
    
    Args:
        title: Article title text
        summary: Article summary/content text
        fallback_lang: Fallback language code if detection fails
        
    Returns:
        ISO 639-1 language code
    """
    # Combine title and summary for better detection
    combined_text = f"{title} {summary}".strip()
    
    if not combined_text or len(combined_text.strip()) < 10:
        return fallback_lang
    
    try:
        from langdetect import detect
        
        # Clean text for better detection
        clean = clean_text(combined_text)
        
        # Only detect if we have enough content
        if len(clean.strip()) < 20:
            return fallback_lang
        
        # Detect language
        lang = detect(clean)
        
        # Validate language code
        if lang and len(lang) == 2 and lang.isalpha():
            return lang.lower()
        
        return fallback_lang
        
    except Exception as e:
        logger.debug(f"Language detection failed: {e}")
        return fallback_lang


def normalize_url(url: str) -> str:
    """
    Normalize URL by removing tracking parameters, fragments, and sorting query params.
    
    Args:
        url: Original URL string
        
    Returns:
        Normalized URL string
    """
    if not url:
        return ""
    
    try:
        from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
        
        # Parse the URL
        parsed = urlparse(url.strip())
        
        # Remove fragment (anchor)
        parsed = parsed._replace(fragment='')
        
        # Process query parameters
        if parsed.query:
            # Parse query parameters
            params = parse_qs(parsed.query, keep_blank_values=False)
            
            # Remove common tracking parameters
            tracking_params = {
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                'fbclid', 'gclid', 'msclkid', 'twclid', '_ga', '_gl',
                'ref', 'referrer', 'source', 'campaign_id', 'ad_id',
                'cmpid', 'cid', 'eid', 'ncid', 'mc_cid', 'mc_eid'
            }
            
            # Filter out tracking parameters
            filtered_params = {
                key: value for key, value in params.items() 
                if key.lower() not in tracking_params
            }
            
            # Sort parameters for consistency
            if filtered_params:
                sorted_query = urlencode(
                    sorted(filtered_params.items()),
                    doseq=True
                )
                parsed = parsed._replace(query=sorted_query)
            else:
                parsed = parsed._replace(query='')
        
        # Reconstruct URL
        return urlunparse(parsed)
        
    except Exception as e:
        logger.warning(f"URL normalization failed for '{url}': {e}")
        # Return original URL if normalization fails
        return url.strip()


def sha1_url(url: str) -> str:
    """
    Generate SHA1 hash of normalized URL for duplicate detection.
    
    Args:
        url: URL string
        
    Returns:
        SHA1 hash as hexadecimal string
    """
    if not url:
        return ""
    
    # Normalize URL (remove tracking params, fragments, sort query)
    normalized_url = normalize_url(url)
    
    # Generate SHA1 hash of normalized URL
    return hashlib.sha1(normalized_url.encode('utf-8')).hexdigest()


def compute_simhash(text: str) -> str:
    """
    Compute SimHash for text content similarity detection.
    
    Args:
        text: Text content to hash
        
    Returns:
        SimHash as hexadecimal string
    """
    if not text:
        return "0"
    
    try:
        # Clean text for consistent hashing
        clean = clean_text(text)
        
        # Compute SimHash
        simhash = SimHash(clean)
        
        # Return as hex string
        return hex(simhash.hash)[2:]  # Remove '0x' prefix
        
    except Exception as e:
        logger.warning(f"SimHash computation failed: {e}")
        # Fallback to simple hash
        return hex(hash(text) & 0xFFFFFFFFFFFFFFFF)[2:]


def normalize_entry(entry: Dict[str, Any], source) -> Dict[str, Any]:
    """
    Normalize RSS/Atom entry to consistent format.
    
    Args:
        entry: Raw RSS/Atom entry from parser
        source: Source object with metadata
        
    Returns:
        Normalized entry dictionary with keys:
        - title: Cleaned title text
        - url: Article URL
        - summary: Cleaned summary/description
        - lang: Detected language code
        - published_at: UTC datetime of publication
        - fetched_at: UTC datetime when fetched
        - url_sha1: SHA1 hash of URL
        - text_simhash: SimHash of content
        - payload: Original entry data
    """
    def now_utc() -> datetime:
        """Get current UTC datetime."""
        return datetime.now(timezone.utc)
    
    now_utc_time = now_utc()
    
    # Extract basic fields (handle both dict and namespace objects)
    def get_field(obj, field, default=''):
        if hasattr(obj, 'get'):
            return obj.get(field, default)
        else:
            return getattr(obj, field, default)
    
    title = clean_text(get_field(entry, 'title', ''))
    url = get_field(entry, 'link', '') or get_field(entry, 'url', '')
    
    # Extract and clean content
    summary = ''
    content_sources = [
        get_field(entry, 'content', None),
        get_field(entry, 'summary', None), 
        get_field(entry, 'description', None),
        get_field(entry, 'subtitle', None)
    ]
    
    for content in content_sources:
        if content:
            if isinstance(content, list) and content:
                # Handle content arrays (Atom feeds)
                content = content[0].get('value', '') if isinstance(content[0], dict) else str(content[0])
            summary = clean_text(str(content))
            if summary:
                break
    
    # Parse publication date
    published_raw = (
        get_field(entry, 'published', None) or 
        get_field(entry, 'updated', None) or 
        get_field(entry, 'created', None) or
        get_field(entry, 'pubDate', None)
    )
    
    published_at = to_utc(parse_datetime_guess(published_raw))
    
    # Detect language from title + summary, fallback to source language
    source_lang = getattr(source, 'lang', 'en')
    lang = detect_lang(title, summary, source_lang)
    
    # Generate hashes
    url_sha1 = sha1_url(url)
    text_for_simhash = f"{title} {summary}".strip()
    text_simhash = compute_simhash(text_for_simhash)
    
    # Build normalized entry
    normalized = {
        'title': title,
        'url': url,
        'summary': summary,
        'lang': lang,
        'published_at': published_at,
        'fetched_at': now_utc_time,
        'url_sha1': url_sha1,
        'text_simhash': text_simhash,
        'payload': dict(entry) if hasattr(entry, 'get') else vars(entry)  # Preserve original data
    }
    
    logger.debug(
        "Normalized entry",
        extra={
            'title': title[:50] + '...' if len(title) > 50 else title,
            'url': url,
            'lang': lang,
            'url_sha1': url_sha1[:8] + '...',
            'text_simhash': text_simhash[:8] + '...'
        }
    )
    
    return normalized


def validate_normalized_entry(entry: Dict[str, Any]) -> bool:
    """
    Validate that normalized entry has required fields.
    
    Args:
        entry: Normalized entry dictionary
        
    Returns:
        True if entry is valid, False otherwise
    """
    required_fields = ['title', 'url', 'url_sha1', 'published_at', 'fetched_at']
    
    for field in required_fields:
        if field not in entry:
            logger.warning(f"Missing required field: {field}")
            return False
        
        if not entry[field]:
            logger.warning(f"Empty required field: {field}")
            return False
    
    # Validate URL format (basic check)
    url = entry.get('url', '')
    if not (url.startswith('http://') or url.startswith('https://')):
        logger.warning(f"Invalid URL format: {url}")
        return False
    
    # Validate datetime fields
    for dt_field in ['published_at', 'fetched_at']:
        if not isinstance(entry[dt_field], datetime):
            logger.warning(f"Invalid datetime field {dt_field}: {type(entry[dt_field])}")
            return False
    
    return True


def batch_normalize_entries(entries: list, source) -> list:
    """
    Normalize a batch of RSS/Atom entries.
    
    Args:
        entries: List of raw RSS/Atom entries
        source: Source object with metadata
        
    Returns:
        List of normalized entries (only valid ones)
    """
    normalized_entries = []
    
    for i, entry in enumerate(entries):
        try:
            normalized = normalize_entry(entry, source)
            
            if validate_normalized_entry(normalized):
                normalized_entries.append(normalized)
            else:
                logger.warning(f"Skipping invalid entry {i}: validation failed")
                
        except Exception as e:
            logger.error(f"Error normalizing entry {i}: {e}", extra={'entry_keys': list(entry.keys())})
            continue
    
    logger.info(
        f"Normalized {len(normalized_entries)}/{len(entries)} entries",
        extra={
            'source_url': getattr(source, 'url', 'unknown'),
            'success_rate': len(normalized_entries) / len(entries) if entries else 0
        }
    )
    
    return normalized_entries