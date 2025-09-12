#!/usr/bin/env python3
"""
Enhanced RSS Fetcher Demo with Conditional Caching

This script demonstrates the new RSS fetching capabilities:
- Conditional GET requests with ETag and Last-Modified
- Exponential backoff retry logic
- feedparser integration
- Robust entry mapping

"""

import asyncio
from datetime import datetime
from types import SimpleNamespace

from newsbot.ingestor.rss import RSSFetcher, ParsedFeed


async def demo_enhanced_rss():
    """Demonstrate enhanced RSS fetching with conditional caching."""
    print("🚀 Enhanced RSS Fetcher Demo")
    print("=" * 60)
    
    # Create mock source objects to test different scenarios
    
    # 1. Fresh source (no caching headers)
    fresh_source = SimpleNamespace()
    fresh_source.url = "https://feeds.feedburner.com/oreilly/radar"  # O'Reilly Radar
    fresh_source.etag = None
    fresh_source.last_modified = None
    
    # 2. Source with ETag (simulate cached)
    cached_source = SimpleNamespace() 
    cached_source.url = "https://rss.cnn.com/rss/edition.rss"  # CNN RSS
    cached_source.etag = '"old-etag-value"'
    cached_source.last_modified = None
    
    # 3. Source with Last-Modified (simulate cached)
    time_cached_source = SimpleNamespace()
    time_cached_source.url = "https://feeds.bbci.co.uk/news/rss.xml"  # BBC News
    time_cached_source.etag = None
    time_cached_source.last_modified = datetime(2024, 9, 1, 12, 0, 0)
    
    async with RSSFetcher(timeout=15) as fetcher:
        
        print("📡 Test 1: Fresh fetch (no caching headers)")
        print(f"URL: {fresh_source.url}")
        
        # Test conditional headers generation
        headers = fetcher.get_conditional_headers(fresh_source)
        print(f"Conditional headers: {headers}")
        
        try:
            result = await fetcher.fetch_and_parse(fresh_source)
            print(f"Status: {result.status}")
            print(f"Entries found: {len(result.entries)}")
            if result.etag:
                print(f"ETag received: {result.etag[:50]}...")
            if result.last_modified:
                print(f"Last-Modified: {result.last_modified}")
            
            if result.entries:
                entry = result.entries[0]
                print(f"First entry: {entry.get('title', 'No title')[:80]}...")
                print(f"Link: {entry.get('link', 'No link')}")
                print(f"Published: {entry.get('published', 'No date')}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("-" * 60)
        
        print("📡 Test 2: Source with ETag (may get 304)")
        print(f"URL: {cached_source.url}")
        
        headers = fetcher.get_conditional_headers(cached_source)
        print(f"Conditional headers: {headers}")
        
        try:
            result = await fetcher.fetch_and_parse(cached_source)
            print(f"Status: {result.status}")
            
            if result.status == "not_modified":
                print("✅ Got 304 Not Modified - content cached!")
            else:
                print(f"Entries found: {len(result.entries)}")
                if result.entries:
                    entry = result.entries[0]
                    print(f"First entry: {entry.get('title', 'No title')[:80]}...")
                    
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("-" * 60)
        
        print("📡 Test 3: Source with Last-Modified date")
        print(f"URL: {time_cached_source.url}")
        
        headers = fetcher.get_conditional_headers(time_cached_source)
        print(f"Conditional headers: {headers}")
        
        try:
            result = await fetcher.fetch_and_parse(time_cached_source)
            print(f"Status: {result.status}")
            
            if result.status == "not_modified":
                print("✅ Got 304 Not Modified - content cached!")
            else:
                print(f"Entries found: {len(result.entries)}")
                if result.entries:
                    entry = result.entries[0]
                    print(f"First entry: {entry.get('title', 'No title')[:80]}...")
                    
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n🎯 Key Features Demonstrated:")
    print("   • Conditional GET with If-None-Match (ETag)")
    print("   • Conditional GET with If-Modified-Since")
    print("   • 304 Not Modified handling")
    print("   • feedparser integration")
    print("   • Exponential backoff retry logic")
    print("   • Robust entry mapping with fallbacks")
    print("   • RFC1123 date formatting")
    
    print("\n📊 Entry Mapping Features:")
    print("   • Tolerant link extraction (link, links array, or ID fallback)")
    print("   • Multiple content sources (content, summary, description)")
    print("   • Flexible date parsing (published, updated, created)")
    print("   • Author extraction from multiple formats")
    print("   • Category/tag processing")
    print("   • GUID generation with fallbacks")


async def demo_legacy_compatibility():
    """Test that legacy RSS parser still works."""
    print("\n🔄 Legacy Compatibility Test")
    print("=" * 40)
    
    from newsbot.ingestor.rss import RSSParser
    
    async with RSSParser() as parser:
        try:
            # Test with a simple RSS feed
            items = await parser.fetch_and_parse("https://feeds.feedburner.com/oreilly/radar")
            print(f"✅ Legacy parser: {len(items)} items fetched")
            
            if items:
                item = items[0]
                print(f"First item: {item.title[:50]}...")
                print(f"Type: {type(item).__name__}")
                
        except Exception as e:
            print(f"❌ Legacy compatibility error: {e}")


if __name__ == "__main__":
    print("Note: This demo requires internet connection to fetch real RSS feeds")
    print("Some feeds may return 304 if they haven't been updated recently")
    print()
    
    asyncio.run(demo_enhanced_rss())
    asyncio.run(demo_legacy_compatibility())