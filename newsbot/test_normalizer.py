#!/usr/bin/env python3
"""
Test script for RSS feed entry normalization helpers.

Tests all the helper functions for normalizing RSS/Atom feed entries.
"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from newsbot.ingestor.normalizer import (
    clean_text,
    parse_datetime_guess,
    to_utc,
    detect_lang,
    sha1_url,
    compute_simhash,
    normalize_entry,
    validate_normalized_entry,
    batch_normalize_entries
)
from newsbot.ingestor.rss import RSSFetcher


def test_clean_text():
    """Test HTML/text cleaning function."""
    print("🧹 Testing clean_text function")
    print("-" * 40)
    
    test_cases = [
        ("<p>Hello <b>world</b>!</p>", "Hello world!"),
        ("Multiple   spaces\n\nand\tlines", "Multiple spaces and lines"),
        ("<script>alert('xss')</script>Clean text", "Clean text"),
        ("", ""),
        (None, ""),
        ("<div><p>Nested <em>HTML</em> tags</p></div>", "Nested HTML tags"),
    ]
    
    for html, expected in test_cases:
        result = clean_text(html)
        status = "✅" if result == expected else "❌"
        print(f"{status} Input: {repr(html)}")
        print(f"   Expected: {repr(expected)}")
        print(f"   Got: {repr(result)}")
        print()


def test_parse_datetime_guess():
    """Test datetime parsing function."""
    print("📅 Testing parse_datetime_guess function")
    print("-" * 40)
    
    test_cases = [
        "2024-09-12T15:30:00Z",
        "Wed, 12 Sep 2024 15:30:00 GMT",
        "September 12, 2024 3:30 PM",
        "2024-09-12 15:30:00",
        "invalid date string",
        None,
        datetime.now(),
    ]
    
    for case in test_cases:
        result = parse_datetime_guess(case)
        print(f"Input: {repr(case)}")
        print(f"Result: {result} (type: {type(result).__name__})")
        print(f"UTC: {isinstance(result, datetime)}")
        print()


def test_to_utc():
    """Test UTC conversion function."""
    print("🌍 Testing to_utc function")
    print("-" * 40)
    
    # Test cases
    naive_dt = datetime(2024, 9, 12, 15, 30, 0)
    utc_dt = datetime(2024, 9, 12, 15, 30, 0, tzinfo=timezone.utc)
    
    test_cases = [
        naive_dt,
        utc_dt,
        None,
    ]
    
    for case in test_cases:
        result = to_utc(case)
        print(f"Input: {case}")
        print(f"Result: {result}")
        print(f"Timezone: {result.tzinfo}")
        print()


def test_detect_lang():
    """Test language detection function."""
    print("🗣️ Testing detect_lang function")
    print("-" * 40)
    
    test_cases = [
        ("This is a text written in English language", "en"),
        ("Ceci est un texte écrit en français", "fr"), 
        ("Dies ist ein auf Deutsch geschriebener Text", "de"),
        ("Este es un texto escrito en español", "es"),
        ("Short", None),  # Too short
        ("", None),  # Empty
        (None, None),  # None
    ]
    
    for text, expected_lang in test_cases:
        result = detect_lang(text)
        status = "✅" if result == expected_lang else "🔄"
        print(f"{status} Text: {repr(text)}")
        print(f"   Expected: {expected_lang}")
        print(f"   Detected: {result}")
        print()


def test_sha1_url():
    """Test URL SHA1 hashing function."""
    print("🔗 Testing sha1_url function")
    print("-" * 40)
    
    test_cases = [
        "https://example.com/article/123",
        "https://example.com/article/456",
        "https://example.com/article/123",  # Same as first
        "",
        None,
    ]
    
    hashes = []
    for url in test_cases:
        result = sha1_url(url)
        hashes.append(result)
        print(f"URL: {repr(url)}")
        print(f"SHA1: {result}")
        print()
    
    # Check for duplicates
    print("Duplicate check:")
    print(f"URLs 1 and 3 same hash: {hashes[0] == hashes[2]}")
    print(f"URLs 1 and 2 different hash: {hashes[0] != hashes[1]}")


def test_compute_simhash():
    """Test SimHash computation function."""
    print("🔢 Testing compute_simhash function")
    print("-" * 40)
    
    test_cases = [
        "This is a sample article about technology and innovation",
        "This is a sample article about technology and innovation",  # Same
        "This is a different article about sports and entertainment",
        "Technology innovation sample article",  # Similar words, different order
        "",
        None,
    ]
    
    hashes = []
    for text in test_cases:
        result = compute_simhash(text)
        hashes.append(result)
        print(f"Text: {repr(text)}")
        print(f"SimHash: {result}")
        print()
    
    # Check similarity
    print("Similarity check:")
    print(f"Texts 1 and 2 same hash: {hashes[0] == hashes[1]}")
    print(f"Texts 1 and 3 different hash: {hashes[0] != hashes[2]}")


async def test_normalize_entry():
    """Test entry normalization function."""
    print("📝 Testing normalize_entry function")
    print("-" * 40)
    
    # Create mock source
    source = SimpleNamespace()
    source.lang = "en"
    source.url = "https://example.com/feed.xml"
    
    # Create sample RSS entry
    entry = {
        'title': 'Breaking: <b>Technology News</b> Today',
        'link': 'https://example.com/tech-news-123',
        'summary': '<p>This is a <em>summary</em> of the tech news article.</p>',
        'content': 'Full article content with more details about technology...',
        'published': '2024-09-12T15:30:00Z',
        'author': 'John Doe',
        'categories': ['technology', 'news'],
        'guid': 'tech-news-123'
    }
    
    # Normalize entry
    result = normalize_entry(entry, source)
    
    print("Original entry:")
    for key, value in entry.items():
        print(f"  {key}: {repr(value)}")
    
    print("\nNormalized entry:")
    for key, value in result.items():
        if key == 'payload':
            print(f"  {key}: <original entry data>")
        else:
            print(f"  {key}: {repr(value)}")
    
    # Validate
    is_valid = validate_normalized_entry(result)
    print(f"\nValidation: {'✅ Valid' if is_valid else '❌ Invalid'}")


async def test_with_real_rss():
    """Test normalization with real RSS feed data."""
    print("\n🌐 Testing with real RSS feed")
    print("-" * 40)
    
    # Create mock source
    source = SimpleNamespace()
    source.lang = "en"
    source.url = "http://feeds.bbci.co.uk/news/rss.xml"
    source.etag = None
    source.last_modified = None
    
    try:
        async with RSSFetcher(timeout=10) as fetcher:
            result = await fetcher.fetch_and_parse(source)
            
            if result.status == "ok" and result.entries:
                # Test with first 3 entries
                entries_to_test = result.entries[:3]
                normalized = batch_normalize_entries(entries_to_test, source)
                
                print(f"Processed {len(entries_to_test)} entries")
                print(f"Successfully normalized: {len(normalized)}")
                
                if normalized:
                    entry = normalized[0]
                    print(f"\nFirst normalized entry:")
                    print(f"  Title: {entry['title'][:60]}...")
                    print(f"  URL: {entry['url']}")
                    print(f"  Language: {entry['lang']}")
                    print(f"  Published: {entry['published_at']}")
                    print(f"  URL SHA1: {entry['url_sha1'][:16]}...")
                    print(f"  SimHash: {entry['text_simhash'][:16]}...")
                    
            else:
                print(f"Failed to fetch RSS feed: {result.status}")
                
    except Exception as e:
        print(f"Error testing with real RSS: {e}")


async def main():
    """Run all tests."""
    print("🧪 RSS Feed Entry Normalization Tests")
    print("=" * 60)
    
    test_clean_text()
    test_parse_datetime_guess()
    test_to_utc()
    test_detect_lang()
    test_sha1_url()
    test_compute_simhash()
    await test_normalize_entry()
    await test_with_real_rss()
    
    print("\n✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())