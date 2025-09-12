#!/usr/bin/env python3
"""Test the enhanced RSS fetcher with ETag and If-Modified-Since support."""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from newsbot.ingestor.rss import RSSFetcher


async def test_basic_fetch():
    """Test basic RSS fetching without conditional headers."""
    print("🔍 Testing basic RSS fetch...")
    
    async with RSSFetcher() as fetcher:
        # Test with a reliable RSS feed
        result = await fetcher.fetch("https://feeds.bbci.co.uk/news/rss.xml")
        
        print(f"Status Code: {result.status_code}")
        print(f"ETag: {result.etag}")
        print(f"Last-Modified: {result.last_modified}")
        
        if result.feed:
            print(f"Entries: {len(result.feed.entries)}")
            if result.feed.entries:
                first_entry = result.feed.entries[0]
                print(f"First entry: {first_entry.get('title', 'No title')[:50]}...")
        
        if result.error:
            print(f"Error: {result.error}")
        
        return result


async def test_conditional_fetch():
    """Test conditional fetching with ETag and Last-Modified."""
    print("\n🔄 Testing conditional fetch (should get 304)...")
    
    async with RSSFetcher() as fetcher:
        # First fetch to get headers
        print("First fetch to get headers...")
        result1 = await fetcher.fetch("https://feeds.bbci.co.uk/news/rss.xml")
        
        if result1.status_code != 200:
            print(f"First fetch failed: {result1.status_code} - {result1.error}")
            return
        
        print(f"Got ETag: {result1.etag}")
        print(f"Got Last-Modified: {result1.last_modified}")
        
        # Second fetch with conditional headers
        print("\nSecond fetch with conditional headers...")
        result2 = await fetcher.fetch(
            "https://feeds.bbci.co.uk/news/rss.xml",
            etag=result1.etag,
            last_modified=result1.last_modified
        )
        
        print(f"Status Code: {result2.status_code}")
        
        if result2.status_code == 304:
            print("✅ Got 304 Not Modified - conditional headers working!")
        elif result2.status_code == 200:
            print("⚠️  Got 200 OK - feed was modified or server doesn't support conditional requests")
        else:
            print(f"❌ Unexpected status: {result2.status_code} - {result2.error}")
        
        return result2


async def test_clock_skew_protection():
    """Test clock skew protection for Last-Modified dates."""
    print("\n🕒 Testing clock skew protection...")
    
    fetcher = RSSFetcher()
    
    # Test with future date
    future_date = datetime.now(timezone.utc).replace(year=2030)
    print(f"Testing with future date: {future_date}")
    
    # This would be done internally by _parse_last_modified_header
    result = fetcher._parse_last_modified_header("Mon, 01 Jan 2030 12:00:00 GMT")
    
    if result:
        now = datetime.now(timezone.utc)
        print(f"Parsed date: {result}")
        print(f"Current time: {now}")
        
        if result <= now:
            print("✅ Clock skew protection working - future date clamped to now")
        else:
            print("❌ Clock skew protection failed - future date not handled")
    else:
        print("❌ Failed to parse Last-Modified header")


async def test_header_building():
    """Test conditional header building."""
    print("\n📋 Testing conditional header building...")
    
    fetcher = RSSFetcher()
    
    # Test with ETag only
    headers1 = fetcher._build_conditional_headers(etag='"test-etag-123"')
    print(f"ETag only: {headers1}")
    
    # Test with Last-Modified only
    last_mod = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    headers2 = fetcher._build_conditional_headers(last_modified=last_mod)
    print(f"Last-Modified only: {headers2}")
    
    # Test with both
    headers3 = fetcher._build_conditional_headers(
        etag='"test-etag-123"',
        last_modified=last_mod
    )
    print(f"Both headers: {headers3}")
    
    # Verify RFC1123 format
    if "If-Modified-Since" in headers3:
        if_mod_since = headers3["If-Modified-Since"]
        print(f"RFC1123 format: {if_mod_since}")
        
        # Should look like: "Mon, 01 Jan 2024 12:00:00 GMT"
        if "GMT" in if_mod_since and len(if_mod_since) == 29:
            print("✅ RFC1123 format looks correct")
        else:
            print("❌ RFC1123 format might be incorrect")


async def main():
    """Run all tests."""
    print("🧪 Testing Enhanced RSS Fetcher")
    print("=" * 50)
    
    try:
        # Test basic functionality
        await test_basic_fetch()
        
        # Test conditional requests
        await test_conditional_fetch()
        
        # Test clock skew protection
        await test_clock_skew_protection()
        
        # Test header building
        await test_header_building()
        
        print("\n" + "=" * 50)
        print("✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)