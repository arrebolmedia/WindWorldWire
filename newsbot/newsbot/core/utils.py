"""
Utility functions for NewsBot.

Provides text processing, sanitization, SEO optimization, and formatting utilities.
All functions focus on safety and preventing injection attacks.
"""

import re
import html
import unicodedata
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from urllib.parse import urlparse, quote

# Try to import bleach for HTML sanitization, fallback to basic cleaning
try:
    import bleach
    HAS_BLEACH = True
except ImportError:
    HAS_BLEACH = False

# Allowed HTML tags for safe content rendering
ALLOWED_HTML_TAGS = [
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'ul', 'ol', 'li', 
    'h2', 'h3', 'h4', 'blockquote', 'a', 'span', 'div'
]

ALLOWED_HTML_ATTRIBUTES = {
    'a': ['href', 'title', 'rel'],
    'span': ['class'],
    'div': ['class'],
    'blockquote': ['cite']
}

# Common Spanish stopwords for SEO optimization
SPANISH_STOPWORDS = {
    'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'se', 'no', 'te', 'lo', 'le',
    'da', 'su', 'por', 'son', 'con', 'para', 'al', 'del', 'los', 'las', 'una', 'como',
    'pero', 'sus', 'les', 'me', 'mi', 'nos', 'ni', 'ya', 'yo', 'si', 'muy', 'más',
    'este', 'esta', 'esto', 'ese', 'esa', 'eso', 'aquel', 'aquella', 'aquello'
}


def slugify(text: str, max_length: int = 80) -> str:
    """
    Convert text to URL-safe slug.
    
    Args:
        text: Text to convert
        max_length: Maximum slug length
        
    Returns:
        URL-safe slug
    """
    if not text:
        return ""
    
    # Normalize unicode and remove accents
    normalized = unicodedata.normalize('NFKD', text)
    ascii_only = normalized.encode('ascii', 'ignore').decode('ascii')
    
    # Convert to lowercase
    slug = ascii_only.lower()
    
    # Replace spaces and punctuation with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    
    # Remove consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    
    # Limit length
    if len(slug) > max_length:
        # Try to break at word boundary
        truncated = slug[:max_length]
        last_hyphen = truncated.rfind('-')
        if last_hyphen > max_length * 0.7:  # If hyphen is reasonably close to end
            slug = truncated[:last_hyphen]
        else:
            slug = truncated
    
    return slug or "articulo"  # Fallback if empty


def sanitize_html(content: str, allowed_tags: List[str] = None, strip: bool = False) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.
    
    Args:
        content: HTML content to sanitize
        allowed_tags: List of allowed HTML tags (None for default)
        strip: Whether to strip tags instead of escaping
        
    Returns:
        Sanitized HTML content
    """
    if not content:
        return ""
    
    if allowed_tags is None:
        allowed_tags = ALLOWED_HTML_TAGS
    
    if HAS_BLEACH:
        if strip:
            # Strip all HTML tags
            return bleach.clean(content, tags=[], strip=True)
        else:
            # Clean while preserving allowed tags
            return bleach.clean(
                content,
                tags=allowed_tags,
                attributes=ALLOWED_HTML_ATTRIBUTES,
                strip=True
            )
    else:
        # Fallback: basic HTML stripping with regex
        if strip:
            return re.sub(r'<[^>]+>', '', content)
        else:
            # Simple escape
            return html.escape(content)


def clean_text(text: str) -> str:
    """
    Clean text content by removing extra whitespace and normalizing.
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Normalize unicode
    text = unicodedata.normalize('NFKC', text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Trim
    text = text.strip()
    
    return text


def clamp_length(text: str, min_length: int, max_length: int, suffix: str = "...") -> str:
    """
    Ensure text is within specified length bounds.
    
    Args:
        text: Text to clamp
        min_length: Minimum required length
        max_length: Maximum allowed length
        suffix: Suffix to add when truncating
        
    Returns:
        Text within length bounds
    """
    if not text:
        return ""
    
    # If too short, return as-is (caller should handle)
    if len(text) < min_length:
        return text
    
    # If within bounds, return as-is
    if len(text) <= max_length:
        return text
    
    # If too long, truncate intelligently
    if suffix and len(suffix) < max_length:
        target_length = max_length - len(suffix)
        
        # Try to break at sentence boundary
        sentences = re.split(r'[.!?]', text[:target_length + 50])
        if len(sentences) > 1 and len(sentences[0]) >= target_length * 0.7:
            return sentences[0].strip() + suffix
        
        # Try to break at word boundary
        words = text[:target_length + 20].split()
        if len(words) > 1:
            truncated = ' '.join(words[:-1])
            if len(truncated) <= target_length:
                return truncated + suffix
        
        # Hard truncate
        return text[:target_length].strip() + suffix
    
    return text[:max_length]


def extract_keywords(text: str, max_keywords: int = 10, min_length: int = 3) -> List[str]:
    """
    Extract meaningful keywords from text for SEO.
    
    Args:
        text: Text to analyze
        max_keywords: Maximum number of keywords to return
        min_length: Minimum keyword length
        
    Returns:
        List of keywords sorted by relevance
    """
    if not text:
        return []
    
    # Clean and normalize text
    cleaned = clean_text(text.lower())
    
    # Extract words
    words = re.findall(r'\b[a-záéíóúñü]+\b', cleaned)
    
    # Filter out stopwords and short words
    meaningful_words = [
        word for word in words 
        if len(word) >= min_length and word not in SPANISH_STOPWORDS
    ]
    
    # Count frequency
    from collections import Counter
    word_counts = Counter(meaningful_words)
    
    # Return most frequent words
    return [word for word, count in word_counts.most_common(max_keywords)]


def validate_url(url: str) -> bool:
    """
    Validate if URL is properly formed and safe.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is valid and safe
    """
    if not url:
        return False
    
    try:
        parsed = urlparse(url)
        
        # Must have scheme and netloc
        if not parsed.scheme or not parsed.netloc:
            return False
        
        # Must be http or https
        if parsed.scheme not in ('http', 'https'):
            return False
        
        # Basic security checks
        netloc_lower = parsed.netloc.lower()
        
        # Block localhost and internal IPs
        if any(blocked in netloc_lower for blocked in ['localhost', '127.0.0.1', '0.0.0.0']):
            return False
        
        return True
        
    except Exception:
        return False


def create_excerpt(content: str, max_length: int = 160, prefer_sentences: bool = True) -> str:
    """
    Create excerpt from content for meta descriptions.
    
    Args:
        content: Source content
        max_length: Maximum excerpt length
        prefer_sentences: Whether to prefer complete sentences
        
    Returns:
        Content excerpt
    """
    if not content:
        return ""
    
    # Strip HTML and clean
    clean_content = sanitize_html(content, strip=True)
    clean_content = clean_text(clean_content)
    
    if len(clean_content) <= max_length:
        return clean_content
    
    if prefer_sentences:
        # Try to end at sentence boundary
        truncated = clean_content[:max_length]
        last_period = truncated.rfind('.')
        last_exclamation = truncated.rfind('!')
        last_question = truncated.rfind('?')
        
        last_sentence_end = max(last_period, last_exclamation, last_question)
        
        if last_sentence_end > max_length * 0.6:  # If reasonably close to end
            return clean_content[:last_sentence_end + 1].strip()
    
    # Fallback to word boundary
    words = clean_content[:max_length + 20].split()
    if len(words) > 1:
        truncated = ' '.join(words[:-1])
        if len(truncated) <= max_length:
            return truncated + "..."
    
    # Hard truncate
    return clean_content[:max_length - 3].strip() + "..."


def placeholder():
    """Placeholder function."""
    pass