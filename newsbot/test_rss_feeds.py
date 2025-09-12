#!/usr/bin/env python3
"""
Test RSS Fetcher with Known Working Feeds

Tests the enhanced RSS fetcher with reliable RSS feeds.
"""

import asyncio
from datetime import datetime
from types import SimpleNamespace

from newsbot.ingestor.rss import RSSFetcher


async def test_working_feeds():
    """Test with known working RSS feeds."""
    print("🧪 Testing Enhanced RSS Fetcher")
    print("=" * 50)
    
    # Test feeds that should work
    test_feeds = [
        {
            "name": "BBC News",
            "url": "http://feeds.bbci.co.uk/news/rss.xml"
        },
        {
            "name": "Reuters Top News", 
            "url": "https://feeds.reuters.com/reuters/topNews"
        },
        {
            "name": "NPR News",
            "url": "https://feeds.npr.org/1001/rss.xml"
        }
    ]
    
    async with RSSFetcher(timeout=10) as fetcher:
        for feed_info in test_feeds:
            print(f"📡 Testing: {feed_info['name']}")
            print(f"URL: {feed_info['url']}")
            
            # Create source object
            source = SimpleNamespace()
            source.url = feed_info['url']
            source.etag = None
            source.last_modified = None
            
            try:
                result = await fetcher.fetch_and_parse(source)
                print(f"✅ Status: {result.status}")
                print(f"   Entries: {len(result.entries)}")
                
                if result.etag:
                    print(f"   ETag: {result.etag[:30]}...")
                
                if result.last_modified:
                    print(f"   Last-Modified: {result.last_modified}")
                
                if result.entries:
                    entry = result.entries[0]
                    print(f"   First Title: {entry.get('title', 'No title')[:60]}...")
                    print(f"   Link: {entry.get('link', 'No link')[:60]}...")
                    
                # Test conditional headers
                if result.etag or result.last_modified:
                    print("   Testing conditional fetch...")
                    source.etag = result.etag
                    source.last_modified = result.last_modified
                    
                    headers = fetcher.get_conditional_headers(source)
                    print(f"   Conditional headers: {list(headers.keys())}")
                    
            except Exception as e:
                print(f"❌ Error: {str(e)[:100]}...")
            
            print("-" * 50)


async def test_entry_mapping():
    """Test entry field mapping thoroughly."""
    print("🔍 Testing Entry Field Mapping")
    print("=" * 40)
    
    source = SimpleNamespace()
    source.url = "http://feeds.bbci.co.uk/news/rss.xml"
    source.etag = None
    source.last_modified = None
    
    async with RSSFetcher() as fetcher:
        try:
            result = await fetcher.fetch_and_parse(source)
            
            if result.entries:
                entry = result.entries[0]
                print("📝 Entry Fields:")
                
                # Show all available fields
                for key, value in entry.items():
                    if isinstance(value, str) and len(value) > 80:
                        print(f"   {key}: {value[:80]}...")
                    elif isinstance(value, list) and value:
                        print(f"   {key}: [{len(value)} items] {value[0] if value else ''}")
                    else:
                        print(f"   {key}: {value}")
                        
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_working_feeds())
    asyncio.run(test_entry_mapping())