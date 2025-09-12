# NewsBot Enhanced RSS Fetcher

## Overview

This implementation provides a production-ready RSS/Atom feed fetcher with conditional caching, exponential backoff retry logic, and robust error handling. It replaces the basic RSS parser with a comprehensive solution suitable for production use.

## ✨ Key Features

### 🔄 Conditional Caching
- **ETag Support**: Uses `If-None-Match` headers to avoid re-downloading unchanged content
- **Last-Modified Support**: Uses `If-Modified-Since` headers for time-based caching
- **304 Not Modified Handling**: Properly handles server responses indicating no changes
- **RFC1123 Date Formatting**: Correctly formats dates for HTTP headers

### 🔁 Retry Logic
- **Exponential Backoff**: Implements exponential backoff for rate limiting (429) and server errors (5xx)
- **Configurable Attempts**: Supports up to 3 retry attempts with increasing delays
- **Smart Error Handling**: Only retries on specific error conditions

### 🛡️ Robust Parsing
- **feedparser Integration**: Uses the industry-standard feedparser library
- **Multiple Content Sources**: Extracts content from various fields (content, summary, description)
- **Flexible Date Parsing**: Handles published, updated, and created date fields
- **Author Extraction**: Supports multiple author field formats
- **Category Processing**: Extracts and normalizes tags/categories
- **GUID Generation**: Creates stable identifiers with multiple fallback strategies

### 🔗 Database Integration
- **URL SHA1 Hashing**: Generates SHA1 hashes for duplicate detection
- **Text SimHash**: Supports content similarity detection (placeholder implementation)
- **Structured Payload**: Stores all feed data in JSON format
- **Source Metadata**: Tracks ETags, Last-Modified dates, and error counts

## 📁 File Structure

```
newsbot/
├── core/
│   └── models.py           # Updated database models with enhanced schema
├── ingestor/
│   └── rss.py             # Enhanced RSS fetcher with conditional caching
├── demo_enhanced_rss.py   # Comprehensive demo of new features
├── test_rss_feeds.py      # Tests with working RSS feeds
└── test_integration.py    # Integration test with database models
```

## 🚀 Usage Examples

### Basic Usage

```python
from newsbot.ingestor.rss import RSSFetcher
from types import SimpleNamespace

# Create source object
source = SimpleNamespace()
source.url = "https://feeds.example.com/rss.xml"
source.etag = None
source.last_modified = None

# Fetch and parse
async with RSSFetcher(timeout=15) as fetcher:
    result = await fetcher.fetch_and_parse(source)
    
    if result.status == "ok":
        print(f"Found {len(result.entries)} entries")
        # Update source with caching info
        source.etag = result.etag
        source.last_modified = result.last_modified
    
    elif result.status == "not_modified":
        print("Feed unchanged, using cached content")
    
    else:
        print(f"Error: {result.error}")
```

### Conditional Caching

```python
# On subsequent requests, conditional headers are automatically used
headers = fetcher.get_conditional_headers(source)
# Returns: {'If-None-Match': '"etag-value"'} or
#          {'If-Modified-Since': 'Wed, 12 Sep 2024 15:30:00 GMT'}

result = await fetcher.fetch_and_parse(source)
# May return status="not_modified" if content unchanged
```

### Legacy Compatibility

```python
# Old RSSParser still works but shows deprecation warning
from newsbot.ingestor.rss import RSSParser

async with RSSParser() as parser:
    items = await parser.fetch_and_parse(url)
    # Returns list of RSSItem objects (legacy format)
```

## 🏗️ Database Schema Updates

The database models have been updated to support the enhanced fetcher:

### Source Model
```python
class Source(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    lang: Mapped[str] = mapped_column(String(10), nullable=False)
    etag: Mapped[Optional[str]] = mapped_column(String(255))           # NEW
    last_modified: Mapped[Optional[datetime]] = mapped_column(DateTime) # NEW
    error_count: Mapped[int] = mapped_column(Integer, default=0)       # NEW
```

### RawItem Model
```python
class RawItem(Base):
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey('sources.id'))
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    url_sha1: Mapped[str] = mapped_column(String(40), nullable=False, index=True) # NEW
    text_simhash: Mapped[int] = mapped_column(BigInteger, index=True)             # NEW
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)                   # NEW
```

## 📊 Performance Benefits

### Bandwidth Savings
- **304 Responses**: Eliminates unnecessary data transfer for unchanged feeds
- **Conditional Requests**: Reduces server load and bandwidth usage
- **Smart Caching**: Automatic cache management with proper header handling

### Error Resilience
- **Exponential Backoff**: Prevents overwhelming servers during high load
- **Error Tracking**: Monitors and records error rates per source
- **Graceful Degradation**: Continues operation even when some feeds fail

### Data Integrity
- **Duplicate Detection**: SHA1 hashing prevents duplicate entries
- **Content Similarity**: SimHash support for near-duplicate detection
- **Structured Storage**: JSON payload preserves all feed metadata

## 🧪 Testing

Three comprehensive test files are provided:

1. **`demo_enhanced_rss.py`**: Complete feature demonstration
2. **`test_rss_feeds.py`**: Tests with known working RSS feeds
3. **`test_integration.py`**: Integration testing with database models

Run tests with:
```bash
python newsbot/demo_enhanced_rss.py
python newsbot/test_rss_feeds.py
python newsbot/test_integration.py
```

## 🔮 Future Enhancements

- **SimHash Implementation**: Replace placeholder with real simhash library
- **Feed Discovery**: Automatic detection of RSS/Atom feeds from websites
- **Content Extraction**: Full-text extraction from article URLs
- **Machine Learning**: Content classification and quality scoring
- **Monitoring**: Real-time dashboards for feed health and performance

## 📋 Migration Notes

### From Basic RSS Parser
1. Update import statements to use `RSSFetcher` instead of `RSSParser`
2. Handle `ParsedFeed` result objects instead of lists
3. Update database schema to include new fields
4. Implement caching logic in your application

### Database Migration
```sql
-- Add new columns to sources table
ALTER TABLE sources ADD COLUMN etag VARCHAR(255);
ALTER TABLE sources ADD COLUMN last_modified DATETIME;
ALTER TABLE sources ADD COLUMN error_count INTEGER DEFAULT 0;

-- Add new columns to raw_items table
ALTER TABLE raw_items ADD COLUMN url_sha1 VARCHAR(40) NOT NULL;
ALTER TABLE raw_items ADD COLUMN text_simhash BIGINT;
ALTER TABLE raw_items ADD COLUMN payload JSON NOT NULL;

-- Add indexes for performance
CREATE INDEX idx_raw_items_url_sha1 ON raw_items(url_sha1);
CREATE INDEX idx_raw_items_text_simhash ON raw_items(text_simhash);
```

---

This enhanced RSS fetcher provides a solid foundation for a production news aggregation system with proper caching, error handling, and data integrity features.