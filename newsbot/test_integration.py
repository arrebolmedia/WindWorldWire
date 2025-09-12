#!/usr/bin/env python3
"""
Integration Test: RSS Fetcher + Database Models

Shows how the enhanced RSS fetcher integrates with our database models.
"""

import asyncio
import hashlib
from datetime import datetime
from types import SimpleNamespace

from newsbot.ingestor.rss import RSSFetcher


def create_mock_source():
    """Create a mock source object that matches our database model."""
    source = SimpleNamespace()
    source.id = 1
    source.name = "BBC News"
    source.url = "http://feeds.bbci.co.uk/news/rss.xml"
    source.type = "rss"
    source.lang = "en"
    source.etag = None  # No cached ETag initially
    source.last_modified = None  # No cached Last-Modified initially
    source.error_count = 0
    source.created_at = datetime.now()
    source.updated_at = datetime.now()
    return source


def create_raw_item_from_entry(entry, source_id):
    """Convert RSS entry to RawItem format matching our database model."""
    # Generate URL SHA1 hash for duplicate detection
    url = entry.get('link', '')
    url_sha1 = hashlib.sha1(url.encode()).hexdigest() if url else None
    
    # Create text content for similarity hashing
    text_content = f"{entry.get('title', '')} {entry.get('summary', '')}"
    # Mock simhash (would use real simhash library in production)
    text_simhash = hash(text_content) & 0xFFFFFFFFFFFFFFFF  # 64-bit hash
    
    # Create payload with all entry data
    payload = {
        'title': entry.get('title'),
        'link': entry.get('link'),
        'summary': entry.get('summary'),
        'content': entry.get('content'),
        'published': entry.get('published'),
        'author': entry.get('author'),
        'categories': entry.get('categories', []),
        'guid': entry.get('guid'),
        'raw_data': entry.get('raw_data', {})
    }
    
    raw_item = SimpleNamespace()
    raw_item.source_id = source_id
    raw_item.url = url
    raw_item.url_sha1 = url_sha1
    raw_item.text_simhash = text_simhash
    raw_item.payload = payload
    raw_item.created_at = datetime.now()
    
    return raw_item


async def integration_test():
    """Test RSS fetcher integration with database models."""
    print("🔗 RSS Fetcher + Database Models Integration Test")
    print("=" * 60)
    
    # Create mock source
    source = create_mock_source()
    print(f"📋 Source: {source.name}")
    print(f"   URL: {source.url}")
    print(f"   Initial ETag: {source.etag}")
    print(f"   Initial Last-Modified: {source.last_modified}")
    print()
    
    async with RSSFetcher(timeout=10) as fetcher:
        try:
            # First fetch - no caching headers
            print("🔄 First fetch (no caching)...")
            result = await fetcher.fetch_and_parse(source)
            
            print(f"✅ Status: {result.status}")
            print(f"   Entries fetched: {len(result.entries)}")
            
            # Update source with caching info
            if result.etag:
                source.etag = result.etag
                print(f"   📌 Stored ETag: {result.etag[:40]}...")
            
            if result.last_modified:
                source.last_modified = result.last_modified
                print(f"   📌 Stored Last-Modified: {result.last_modified}")
            
            # Process entries into RawItem format
            raw_items = []
            for i, entry in enumerate(result.entries[:3]):  # Process first 3 entries
                raw_item = create_raw_item_from_entry(entry, source.id)
                raw_items.append(raw_item)
                
                print(f"\n📄 RawItem {i+1}:")
                print(f"   URL SHA1: {raw_item.url_sha1[:16]}...")
                print(f"   Text SimHash: {raw_item.text_simhash}")
                print(f"   Title: {raw_item.payload['title'][:50]}...")
                print(f"   URL: {raw_item.payload['link'][:50]}...")
            
            print("\n" + "-" * 60)
            
            # Second fetch - with caching headers
            print("🔄 Second fetch (with caching headers)...")
            headers = fetcher.get_conditional_headers(source)
            print(f"   Conditional headers: {list(headers.keys())}")
            
            result2 = await fetcher.fetch_and_parse(source)
            print(f"✅ Status: {result2.status}")
            
            if result2.status == "not_modified":
                print("   🎯 Got 304 Not Modified - using cached content!")
            else:
                print(f"   Entries fetched: {len(result2.entries)}")
                print("   📱 Content was updated")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            # Update error count (would be persisted to database)
            source.error_count += 1
            print(f"   Error count updated to: {source.error_count}")


async def test_duplicate_detection():
    """Test URL SHA1 hashing for duplicate detection."""
    print("\n🔍 Duplicate Detection Test")
    print("=" * 40)
    
    # Test with same URL
    url1 = "https://example.com/article/123"
    url2 = "https://example.com/article/123"  # Same URL
    url3 = "https://example.com/article/456"  # Different URL
    
    hash1 = hashlib.sha1(url1.encode()).hexdigest()
    hash2 = hashlib.sha1(url2.encode()).hexdigest()
    hash3 = hashlib.sha1(url3.encode()).hexdigest()
    
    print(f"URL 1: {url1}")
    print(f"SHA1:  {hash1}")
    print(f"URL 2: {url2}")
    print(f"SHA1:  {hash2}")
    print(f"Same:  {hash1 == hash2}")
    print()
    print(f"URL 3: {url3}")
    print(f"SHA1:  {hash3}")
    print(f"Different: {hash1 != hash3}")


if __name__ == "__main__":
    asyncio.run(integration_test())
    asyncio.run(test_duplicate_detection())