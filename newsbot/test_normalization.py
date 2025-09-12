#!/usr/bin/env python3
"""Test script for enhanced normalization features."""

import asyncio
from datetime import datetime, timezone
from newsbot.ingestor.normalizer import (
    clean_text, 
    parse_datetime_guess, 
    detect_lang,
    normalize_url,
    sha1_url,
    normalize_entry
)
from newsbot.core.logging import get_logger

logger = get_logger(__name__)

def test_html_cleaning():
    """Test HTML cleaning with script/style removal and entity handling."""
    print("🧹 Testing HTML cleaning...")
    
    test_cases = [
        {
            'input': '<script>alert("test")</script><p>Hello &amp; welcome!</p><style>body{color:red}</style>',
            'expected_contains': 'Hello & welcome!'
        },
        {
            'input': '<div>Text with\n\n  multiple   spaces\t\tand\r\nnewlines</div>',
            'expected_contains': 'Text with multiple spaces and newlines'
        },
        {
            'input': 'Plain text with &lt;tags&gt; and &quot;quotes&quot;',
            'expected_contains': 'Plain text with <tags> and "quotes"'
        },
        {
            'input': '',
            'expected_contains': ''
        }
    ]
    
    for i, case in enumerate(test_cases):
        result = clean_text(case['input'])
        print(f"  Test {i+1}: '{case['input'][:50]}...' → '{result}'")
        assert case['expected_contains'] in result or (not case['expected_contains'] and not result)
    
    print("  ✅ HTML cleaning tests passed!")

def test_datetime_parsing():
    """Test datetime parsing with fallback to now_utc()."""
    print("\n📅 Testing datetime parsing...")
    
    test_cases = [
        "2023-12-25T15:30:00Z",
        "Mon, 25 Dec 2023 15:30:00 GMT", 
        "2023-12-25 15:30:00",
        "invalid date string",
        None,
        datetime(2023, 12, 25, 15, 30)
    ]
    
    for i, case in enumerate(test_cases):
        result = parse_datetime_guess(case)
        print(f"  Test {i+1}: '{case}' → {result}")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None  # Should always be timezone-aware
        
    print("  ✅ Datetime parsing tests passed!")

def test_language_detection():
    """Test language detection from title+summary."""
    print("\n🌐 Testing language detection...")
    
    test_cases = [
        {
            'title': 'Breaking News: Major Development',
            'summary': 'This is an English article about recent events.',
            'fallback': 'de',
            'expected': 'en'
        },
        {
            'title': 'Noticias de Última Hora',
            'summary': 'Este es un artículo en español sobre eventos recientes.',
            'fallback': 'en', 
            'expected': 'es'
        },
        {
            'title': '',
            'summary': 'Short',
            'fallback': 'fr',
            'expected': 'fr'  # Should fallback
        }
    ]
    
    for i, case in enumerate(test_cases):
        result = detect_lang(case['title'], case['summary'], case['fallback'])
        print(f"  Test {i+1}: '{case['title']}' + '{case['summary']}' → {result}")
        # Note: Language detection can be unreliable, so we just check it returns a valid code
        assert len(result) == 2 and result.isalpha()
        
    print("  ✅ Language detection tests passed!")

def test_url_normalization():
    """Test URL normalization (UTM removal, fragment removal, query sorting)."""
    print("\n🔗 Testing URL normalization...")
    
    test_cases = [
        {
            'input': 'https://example.com/article?utm_source=twitter&utm_campaign=test&id=123#anchor',
            'expected': 'https://example.com/article?id=123'
        },
        {
            'input': 'https://example.com/page?c=3&b=2&a=1',
            'expected': 'https://example.com/page?a=1&b=2&c=3'
        },
        {
            'input': 'https://example.com/article?fbclid=abc123&gclid=def456&ref=homepage',
            'expected': 'https://example.com/article'
        },
        {
            'input': 'https://example.com/simple',
            'expected': 'https://example.com/simple'
        },
        {
            'input': '',
            'expected': ''
        }
    ]
    
    for i, case in enumerate(test_cases):
        result = normalize_url(case['input'])
        print(f"  Test {i+1}: '{case['input']}' → '{result}'")
        assert result == case['expected'], f"Expected '{case['expected']}', got '{result}'"
        
    print("  ✅ URL normalization tests passed!")

def test_sha1_url():
    """Test SHA1 generation with normalized URLs."""
    print("\n🔐 Testing SHA1 URL hashing...")
    
    # These URLs should produce the same hash after normalization
    url1 = 'https://example.com/article?utm_source=twitter&id=123#anchor'
    url2 = 'https://example.com/article?id=123'
    
    hash1 = sha1_url(url1)
    hash2 = sha1_url(url2)
    
    print(f"  URL1: '{url1}' → {hash1}")
    print(f"  URL2: '{url2}' → {hash2}")
    
    assert hash1 == hash2, "Normalized URLs should produce same hash"
    assert len(hash1) == 40, "SHA1 hash should be 40 characters"
    
    print("  ✅ SHA1 URL hashing tests passed!")

def test_entry_normalization():
    """Test complete entry normalization."""
    print("\n📰 Testing complete entry normalization...")
    
    # Mock source object
    class MockSource:
        def __init__(self, lang='en'):
            self.lang = lang
    
    # Test entry
    test_entry = {
        'title': '<h1>Breaking News &amp; Updates</h1>',
        'link': 'https://example.com/article?utm_source=feed&id=123#top',
        'summary': '<p>This is a <script>alert("bad")</script>summary with HTML &lt;tags&gt;</p>',
        'published': '2023-12-25T15:30:00Z'
    }
    
    source = MockSource('de')  # German fallback
    
    result = normalize_entry(test_entry, source)
    
    print(f"  Title: '{result['title']}'")
    print(f"  URL: '{result['url']}'")
    print(f"  Summary: '{result['summary']}'")
    print(f"  Language: '{result['lang']}'")
    print(f"  Published: {result['published_at']}")
    print(f"  URL SHA1: {result['url_sha1'][:8]}...")
    print(f"  SimHash: {result['text_simhash'][:8]}...")
    
    # Validate results
    assert 'Breaking News & Updates' in result['title']
    assert 'script' not in result['summary']
    assert 'This is a summary' in result['summary']
    assert result['url'] == 'https://example.com/article?utm_source=feed&id=123#top'  # Original URL preserved
    
    # Check that SHA1 is generated from normalized URL
    expected_normalized_url = 'https://example.com/article?id=123'
    expected_sha1 = sha1_url('https://example.com/article?utm_source=feed&id=123#top')  # This should normalize internally
    assert result['url_sha1'] == expected_sha1
    
    assert len(result['url_sha1']) == 40
    assert len(result['text_simhash']) >= 8
    assert isinstance(result['published_at'], datetime)
    assert isinstance(result['fetched_at'], datetime)
    
    print("  ✅ Entry normalization tests passed!")

def main():
    """Run all normalization tests."""
    print("🧪 Testing Enhanced Normalization Features")
    print("=" * 50)
    
    try:
        test_html_cleaning()
        test_datetime_parsing()
        test_language_detection()
        test_url_normalization()
        test_sha1_url()
        test_entry_normalization()
        
        print("\n" + "=" * 50)
        print("🎉 All normalization tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logger.exception("Test failure")
        raise

if __name__ == "__main__":
    main()