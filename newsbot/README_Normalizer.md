# NewsBot RSS Feed Entry Normalizer

## Overview

The RSS Feed Entry Normalizer provides a comprehensive set of helper functions to normalize raw RSS/Atom feed entries into a consistent format for storage and processing. It handles text cleaning, datetime parsing, language detection, and content hashing.

## 🛠️ Core Functions

### `clean_text(html_or_text: str) -> str`

Cleans HTML/text content by stripping tags and normalizing whitespace.

**Features:**
- Uses BeautifulSoup with lxml parser for robust HTML tag removal
- Normalizes whitespace (multiple spaces, tabs, newlines)
- Fallback to regex-based cleaning if parsing fails
- Handles empty/None input gracefully

**Example:**
```python
from newsbot.ingestor.normalizer import clean_text

# Clean HTML content
html = "<p>Breaking: <b>Tech News</b> Today!</p>"
clean = clean_text(html)
# Result: "Breaking: Tech News Today!"

# Normalize whitespace
text = "Multiple   spaces\n\nand\tlines"
clean = clean_text(text)
# Result: "Multiple spaces and lines"
```

### `parse_datetime_guess(value) -> datetime`

Parses datetime from various formats with intelligent fallback.

**Features:**
- Uses dateutil.parser for flexible parsing
- Handles string, datetime, or other input types
- Falls back to current UTC time if parsing fails
- Supports multiple datetime formats (ISO, RFC, human-readable)

**Example:**
```python
from newsbot.ingestor.normalizer import parse_datetime_guess

# Parse various formats
dt1 = parse_datetime_guess("2024-09-12T15:30:00Z")
dt2 = parse_datetime_guess("Wed, 12 Sep 2024 15:30:00 GMT")
dt3 = parse_datetime_guess("September 12, 2024 3:30 PM")
# All return datetime objects
```

### `to_utc(dt: datetime) -> datetime`

Converts datetime to UTC timezone.

**Features:**
- Handles both naive and timezone-aware datetimes
- Assumes naive datetimes are UTC
- Converts timezone-aware datetimes to UTC
- Returns current UTC time for None input

**Example:**
```python
from newsbot.ingestor.normalizer import to_utc
from datetime import datetime, timezone

# Convert naive datetime (assumes UTC)
naive_dt = datetime(2024, 9, 12, 15, 30, 0)
utc_dt = to_utc(naive_dt)
# Result: 2024-09-12 15:30:00+00:00

# Convert timezone-aware datetime
import pytz
est = pytz.timezone('US/Eastern')
est_dt = est.localize(datetime(2024, 9, 12, 11, 30, 0))
utc_dt = to_utc(est_dt)
# Result: 2024-09-12 15:30:00+00:00
```

### `detect_lang(text: str) -> Optional[str]`

Detects language of text using lightweight detection.

**Features:**
- Uses langdetect library with try/except protection
- Requires minimum text length for reliable detection
- Returns ISO 639-1 language codes (e.g., 'en', 'fr', 'de')
- Returns None for short text, empty input, or detection failures

**Example:**
```python
from newsbot.ingestor.normalizer import detect_lang

# Detect various languages
en = detect_lang("This is a text written in English")  # 'en'
fr = detect_lang("Ceci est un texte en français")      # 'fr'
de = detect_lang("Dies ist ein deutscher Text")        # 'de'
none = detect_lang("Short")                             # None (too short)
```

### `sha1_url(url: str) -> str`

Generates SHA1 hash of URL for duplicate detection.

**Features:**
- Normalizes URL by stripping whitespace
- Uses UTF-8 encoding for consistent hashing
- Returns hexadecimal string representation
- Handles empty/None input gracefully

**Example:**
```python
from newsbot.ingestor.normalizer import sha1_url

url1 = "https://example.com/article/123"
url2 = "https://example.com/article/123"  # Same URL
url3 = "https://example.com/article/456"  # Different URL

hash1 = sha1_url(url1)  # 'bd8ed3ed2302fc6196fee686c2b326a2ffbcbe93'
hash2 = sha1_url(url2)  # Same hash as hash1
hash3 = sha1_url(url3)  # Different hash

print(hash1 == hash2)  # True (same URL)
print(hash1 != hash3)  # True (different URLs)
```

### `compute_simhash(text: str) -> str`

Computes SimHash for text content similarity detection.

**Features:**
- Uses NewsBot's SimHash implementation from `newsbot.core.simhash`
- Cleans text before hashing for consistency
- Returns hexadecimal string representation
- Fallback to simple hash if SimHash computation fails

**Example:**
```python
from newsbot.ingestor.normalizer import compute_simhash

text1 = "Technology innovation in modern society"
text2 = "Technology innovation in modern society"  # Same
text3 = "Sports entertainment in modern culture"   # Different

hash1 = compute_simhash(text1)  # 'a1b2c3d4e5f6...'
hash2 = compute_simhash(text2)  # Same as hash1
hash3 = compute_simhash(text3)  # Different hash

print(hash1 == hash2)  # True (identical content)
print(hash1 != hash3)  # True (different content)
```

## 🎯 Main Normalization Function

### `normalize_entry(entry: Dict[str, Any], source) -> Dict[str, Any]`

Normalizes RSS/Atom entry to consistent format.

**Input:** Raw RSS/Atom entry dictionary and source object
**Output:** Normalized entry with standardized fields

**Normalized Entry Fields:**
- `title`: Cleaned title text
- `url`: Article URL  
- `summary`: Cleaned summary/description
- `lang`: Detected or source language code
- `published_at`: UTC datetime of publication
- `fetched_at`: UTC datetime when fetched
- `url_sha1`: SHA1 hash of URL for duplicate detection
- `text_simhash`: SimHash of content for similarity detection
- `payload`: Original entry data preserved

**Example:**
```python
from newsbot.ingestor.normalizer import normalize_entry
from types import SimpleNamespace

# Create source object
source = SimpleNamespace()
source.lang = "en"

# Raw RSS entry
entry = {
    'title': 'Breaking: <b>Tech News</b>',
    'link': 'https://example.com/news/123',
    'summary': '<p>Summary of the news...</p>',
    'published': '2024-09-12T15:30:00Z',
    'author': 'John Doe'
}

# Normalize
normalized = normalize_entry(entry, source)

# Result structure:
{
    'title': 'Breaking: Tech News',
    'url': 'https://example.com/news/123',
    'summary': 'Summary of the news...',
    'lang': 'en',
    'published_at': datetime(2024, 9, 12, 15, 30, tzinfo=timezone.utc),
    'fetched_at': datetime(2025, 9, 12, 22, 0, 0, tzinfo=timezone.utc),
    'url_sha1': '45c9ff6be6f09229f7a6593390ec57c39f7dd0bb',
    'text_simhash': '9105e0d3895f9828',
    'payload': {
        'title': 'Breaking: <b>Tech News</b>',
        'link': 'https://example.com/news/123',
        # ... original entry data
    }
}
```

## 🔍 Validation and Batch Processing

### `validate_normalized_entry(entry: Dict[str, Any]) -> bool`

Validates that normalized entry has all required fields and valid data.

**Validation Checks:**
- Required fields present: title, url, url_sha1, published_at, fetched_at
- No empty required fields
- Valid URL format (http/https)
- Valid datetime objects for date fields

### `batch_normalize_entries(entries: list, source) -> list`

Normalizes a batch of RSS/Atom entries with error handling.

**Features:**
- Processes list of raw entries
- Validates each normalized entry
- Skips invalid entries with logging
- Returns only successfully normalized entries
- Provides batch statistics

**Example:**
```python
from newsbot.ingestor.normalizer import batch_normalize_entries

# Process multiple entries
raw_entries = [entry1, entry2, entry3]  # Raw RSS entries
normalized = batch_normalize_entries(raw_entries, source)

# Returns only valid normalized entries
# Logs statistics: "Normalized 3/3 entries"
```

## 📊 Integration with RSS Fetcher

The normalizer integrates seamlessly with the enhanced RSS fetcher:

```python
from newsbot.ingestor.rss import RSSFetcher
from newsbot.ingestor.normalizer import batch_normalize_entries

async with RSSFetcher() as fetcher:
    # Fetch RSS feed
    result = await fetcher.fetch_and_parse(source)
    
    if result.status == "ok":
        # Normalize all entries
        normalized = batch_normalize_entries(result.entries, source)
        
        # Store in database, check for duplicates, etc.
        for entry in normalized:
            # Use entry['url_sha1'] for duplicate detection
            # Use entry['text_simhash'] for similarity detection
            # Store entry['payload'] as JSON in database
            pass
```

## 🎛️ Configuration and Dependencies

**Required Dependencies:**
- `beautifulsoup4` - HTML parsing and cleaning
- `lxml` - Fast XML/HTML parser
- `python-dateutil` - Flexible datetime parsing  
- `pytz` - Timezone handling
- `langdetect` - Language detection

**Installation:**
```bash
pip install beautifulsoup4 lxml python-dateutil pytz langdetect
```

## 🚀 Performance Characteristics

**Text Cleaning:**
- BeautifulSoup parsing: ~1ms per entry
- Regex fallback: ~0.1ms per entry

**Language Detection:**
- Fast detection: ~2-5ms per entry
- Requires minimum 20 characters for reliability

**SimHash Computation:**
- Text processing: ~1-3ms per entry
- Consistent across different text lengths

**Overall Normalization:**
- ~5-10ms per entry (including all operations)
- Suitable for real-time feed processing

## 🔧 Error Handling

All functions include comprehensive error handling:
- Graceful fallbacks for parsing failures
- Detailed logging with context
- Never raises exceptions (returns defaults instead)
- Preserves original data in case of errors

## 🧪 Testing

Comprehensive test suite available in `test_normalizer.py`:

```bash
python newsbot/test_normalizer.py
```

Tests cover:
- All individual helper functions
- Real RSS feed processing
- Error conditions and edge cases
- Performance characteristics
- Integration with RSS fetcher

---

The RSS Feed Entry Normalizer provides a robust foundation for processing RSS/Atom feeds with proper text cleaning, datetime handling, language detection, and content hashing suitable for production news aggregation systems.