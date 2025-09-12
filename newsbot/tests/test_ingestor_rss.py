"""Tests for RSS ingestion functionality."""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
from types import SimpleNamespace

from newsbot.ingestor.normalizer import normalize_entry
from newsbot.core.simhash import simhash, hamming_distance
from newsbot.ingestor.rss import RSSFetcher, FetchResult


class TestNormalizeEntry:
    """Tests for RSS entry normalization."""
    
    @pytest.fixture
    def minimal_entry(self):
        """Minimal RSS entry for testing."""
        entry = SimpleNamespace()
        entry.title = "Test Article Title"
        entry.link = "https://example.com/article/123"
        entry.summary = "This is a test article summary with enough content."
        entry.published = "Wed, 01 Jan 2024 12:00:00 GMT"
        entry.updated = None
        entry.author = None
        entry.tags = []
        return entry
    
    @pytest.fixture
    def detailed_entry(self):
        """Detailed RSS entry for testing."""
        entry = SimpleNamespace()
        entry.title = "  Breaking News: Important Update  "
        entry.link = "https://example.com/article/456?utm_source=rss&ref=social"
        entry.summary = "<p>This is a <strong>detailed</strong> summary with HTML tags.</p>"
        entry.published = "2024-01-01T15:30:00Z"
        entry.updated = "2024-01-01T16:00:00Z"
        entry.author = "Jane Doe"
        entry.tags = [{"term": "technology"}, {"term": "news"}]
        entry.content = [{"value": "<div>Full content here with more details.</div>"}]
        return entry
    
    def test_normalize_entry_basic(self, minimal_entry):
        """Test basic entry normalization with minimal fields."""
        source_url = "https://example.com/rss"
        
        normalized = normalize_entry(minimal_entry, source_url)
        
        assert normalized is not None
        assert normalized["title"] == "Test Article Title"
        assert normalized["url"] == "https://example.com/article/123"
        assert normalized["summary"] == "This is a test article summary with enough content."
        
        # Check UTC datetime conversion
        assert normalized["published_at"] is not None
        assert isinstance(normalized["published_at"], datetime)
        assert normalized["published_at"].tzinfo == timezone.utc
        
        # Check URL SHA1 generation
        assert normalized["url_sha1"] is not None
        assert len(normalized["url_sha1"]) == 40  # SHA1 hex length
        
        # Check fetched_at is set
        assert normalized["fetched_at"] is not None
        assert isinstance(normalized["fetched_at"], datetime)
        assert normalized["fetched_at"].tzinfo == timezone.utc
    
    def test_normalize_entry_detailed(self, detailed_entry):
        """Test normalization with all fields populated."""
        source_url = "https://example.com/rss"
        
        normalized = normalize_entry(detailed_entry, source_url)
        
        assert normalized is not None
        
        # Test title cleaning
        assert normalized["title"] == "Important Update"  # "Breaking News:" removed
        
        # Test URL cleaning (UTM parameters removed)
        assert "utm_source" not in normalized["url"]
        assert "ref=" not in normalized["url"]
        assert normalized["url"] == "https://example.com/article/456"
        
        # Test HTML cleaning in summary
        assert "<p>" not in normalized["summary"]
        assert "<strong>" not in normalized["summary"]
        assert "detailed" in normalized["summary"]
        
        # Test ISO datetime parsing
        assert normalized["published_at"].year == 2024
        assert normalized["published_at"].month == 1
        assert normalized["published_at"].day == 1
        
        # Test language detection
        assert normalized["lang"] is not None
        
        # Test payload contains raw data
        assert "payload" in normalized
        assert isinstance(normalized["payload"], dict)
    
    def test_normalize_entry_invalid(self):
        """Test handling of invalid entries."""
        # Missing required fields
        entry = SimpleNamespace()
        entry.title = None
        entry.link = None
        entry.summary = None
        
        normalized = normalize_entry(entry, "https://example.com/rss")
        assert normalized is None
        
        # Invalid URL
        entry = SimpleNamespace()
        entry.title = "Valid Title"
        entry.link = "not-a-valid-url"
        entry.summary = "Valid summary"
        entry.published = "Wed, 01 Jan 2024 12:00:00 GMT"
        
        normalized = normalize_entry(entry, "https://example.com/rss")
        assert normalized is None


class TestSimHashHamming:
    """Tests for SimHash and Hamming distance."""
    
    def test_simhash_hamming_similar(self):
        """Test that similar texts have small Hamming distance."""
        text1 = "Breaking news about the latest technology developments in artificial intelligence"
        text2 = "Breaking news about latest technology developments in artificial intelligence"  # Very similar
        
        hash1 = simhash(text1)
        hash2 = simhash(text2)
        
        distance = hamming_distance(hash1, hash2)
        
        # Similar texts should have small distance (< 4 for our dedup threshold)
        assert distance < 4
        assert distance >= 0
    
    def test_simhash_hamming_different(self):
        """Test that different texts have larger Hamming distance."""
        text1 = "Breaking news about technology developments"
        text2 = "Cooking recipes for delicious pasta dishes"
        
        hash1 = simhash(text1)
        hash2 = simhash(text2)
        
        distance = hamming_distance(hash1, hash2)
        
        # Different texts should have larger distance
        assert distance > 10
    
    def test_simhash_identical(self):
        """Test that identical texts have zero distance."""
        text = "This is exactly the same text content"
        
        hash1 = simhash(text)
        hash2 = simhash(text)
        
        distance = hamming_distance(hash1, hash2)
        
        # Identical texts should have zero distance
        assert distance == 0
    
    def test_simhash_edge_cases(self):
        """Test SimHash edge cases."""
        # Empty text
        hash_empty = simhash("")
        assert len(hash_empty) == 64  # 64-bit hash as hex string
        
        # Single word
        hash_single = simhash("word")
        assert len(hash_single) == 64
        
        # Very long text
        long_text = " ".join(["word"] * 1000)
        hash_long = simhash(long_text)
        assert len(hash_long) == 64


class TestFetch304Headers:
    """Tests for HTTP 304 handling with ETag/Last-Modified."""
    
    @pytest.fixture
    def sample_rss_xml(self):
        """Sample RSS XML for testing."""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title>Test Article</title>
                    <link>https://example.com/article1</link>
                    <description>Test description</description>
                    <pubDate>Wed, 01 Jan 2024 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
    
    @pytest.mark.asyncio
    async def test_fetch_304_with_etag(self, sample_rss_xml):
        """Test HTTP 304 response when ETag matches."""
        with patch('httpx.AsyncClient') as mock_client:
            # Mock 304 response
            mock_response = Mock()
            mock_response.status_code = 304
            mock_response.headers = {
                "etag": '"test-etag-123"',
                "last-modified": "Wed, 01 Jan 2024 12:00:00 GMT"
            }
            mock_response.text = ""
            mock_response.raise_for_status = Mock()
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            fetcher = RSSFetcher()
            result = await fetcher.fetch(
                "https://example.com/rss",
                etag='"test-etag-123"'
            )
            
            assert result.status_code == 304
            assert result.feed is None  # No content on 304
            assert result.etag == '"test-etag-123"'
            
            # Verify correct headers were sent
            mock_client.return_value.__aenter__.return_value.get.assert_called_once()
            call_kwargs = mock_client.return_value.__aenter__.return_value.get.call_args[1]
            assert 'If-None-Match' in call_kwargs['headers']
            assert call_kwargs['headers']['If-None-Match'] == '"test-etag-123"'
    
    @pytest.mark.asyncio
    async def test_fetch_304_with_last_modified(self, sample_rss_xml):
        """Test HTTP 304 response when Last-Modified matches."""
        with patch('httpx.AsyncClient') as mock_client:
            # Mock 304 response
            mock_response = Mock()
            mock_response.status_code = 304
            mock_response.headers = {
                "last-modified": "Wed, 01 Jan 2024 12:00:00 GMT"
            }
            mock_response.text = ""
            mock_response.raise_for_status = Mock()
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            fetcher = RSSFetcher()
            last_modified = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            
            result = await fetcher.fetch(
                "https://example.com/rss",
                last_modified=last_modified
            )
            
            assert result.status_code == 304
            assert result.feed is None
            
            # Verify correct headers were sent
            call_kwargs = mock_client.return_value.__aenter__.return_value.get.call_args[1]
            assert 'If-Modified-Since' in call_kwargs['headers']
    
    @pytest.mark.asyncio
    async def test_fetch_200_with_content(self, sample_rss_xml):
        """Test HTTP 200 response with content."""
        with patch('httpx.AsyncClient') as mock_client:
            # Mock 200 response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {
                "etag": '"new-etag-456"',
                "last-modified": "Thu, 02 Jan 2024 12:00:00 GMT",
                "content-type": "application/rss+xml"
            }
            mock_response.text = sample_rss_xml
            mock_response.raise_for_status = Mock()
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            fetcher = RSSFetcher()
            result = await fetcher.fetch("https://example.com/rss")
            
            assert result.status_code == 200
            assert result.feed is not None
            assert len(result.feed.entries) == 1
            assert result.etag == '"new-etag-456"'
            assert result.last_modified is not None


class TestPipelineInsertsAndDedup:
    """Tests for pipeline insertion and deduplication."""
    
    @pytest.fixture
    def duplicate_rss_xml(self):
        """RSS XML with duplicate entries (same URL)."""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title>First Article</title>
                    <link>https://example.com/same-article</link>
                    <description>First version of the article</description>
                    <pubDate>Wed, 01 Jan 2024 12:00:00 GMT</pubDate>
                </item>
                <item>
                    <title>Same Article Different Title</title>
                    <link>https://example.com/same-article</link>
                    <description>Second version of same article</description>
                    <pubDate>Thu, 02 Jan 2024 12:00:00 GMT</pubDate>
                </item>
                <item>
                    <title>Different Article</title>
                    <link>https://example.com/different-article</link>
                    <description>This is a completely different article</description>
                    <pubDate>Fri, 03 Jan 2024 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
    
    def test_duplicate_url_detection(self, duplicate_rss_xml):
        """Test that duplicate URLs are detected during normalization."""
        import feedparser
        
        # Parse the RSS
        feed = feedparser.parse(duplicate_rss_xml)
        entries = feed.entries
        
        # Normalize all entries
        normalized_entries = []
        for entry in entries:
            normalized = normalize_entry(entry, "https://example.com/rss")
            if normalized:
                normalized_entries.append(normalized)
        
        assert len(normalized_entries) == 3  # All should normalize successfully
        
        # Check that duplicate URLs have same url_sha1
        url_sha1_values = [entry["url_sha1"] for entry in normalized_entries]
        
        # First two entries have same URL, should have same SHA1
        assert url_sha1_values[0] == url_sha1_values[1]
        
        # Third entry has different URL, should have different SHA1
        assert url_sha1_values[0] != url_sha1_values[2]
    
    def test_simhash_dedup_detection(self):
        """Test that similar content is detected via SimHash."""
        # Create entries with similar content
        entry1 = SimpleNamespace()
        entry1.title = "Breaking: Major Technology Announcement Today"
        entry1.link = "https://example.com/article1"
        entry1.summary = "A major technology company announced significant developments"
        entry1.published = "Wed, 01 Jan 2024 12:00:00 GMT"
        
        entry2 = SimpleNamespace()
        entry2.title = "Breaking: Major Technology Announcement"  # Slightly different
        entry2.link = "https://example.com/article2"  # Different URL
        entry2.summary = "A major technology company announced significant developments"
        entry2.published = "Wed, 01 Jan 2024 13:00:00 GMT"
        
        # Normalize both entries
        norm1 = normalize_entry(entry1, "https://example.com/rss")
        norm2 = normalize_entry(entry2, "https://example.com/rss")
        
        assert norm1 is not None
        assert norm2 is not None
        
        # Different URLs, so different url_sha1
        assert norm1["url_sha1"] != norm2["url_sha1"]
        
        # But similar content for SimHash comparison
        content1 = f"{norm1['title']} {norm1['summary']}"
        content2 = f"{norm2['title']} {norm2['summary']}"
        
        hash1 = simhash(content1)
        hash2 = simhash(content2)
        
        distance = hamming_distance(hash1, hash2)
        
        # Should be similar enough for deduplication (< 4)
        assert distance < 4
    
    @pytest.mark.asyncio
    async def test_fetch_and_normalize_pipeline(self, duplicate_rss_xml):
        """Test complete fetch and normalize pipeline."""
        with patch('httpx.AsyncClient') as mock_client:
            # Mock successful fetch
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/rss+xml"}
            mock_response.text = duplicate_rss_xml
            mock_response.raise_for_status = Mock()
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            # Fetch RSS
            fetcher = RSSFetcher()
            result = await fetcher.fetch("https://example.com/rss")
            
            assert result.status_code == 200
            assert result.feed is not None
            assert len(result.feed.entries) == 3
            
            # Normalize all entries
            normalized_entries = []
            for entry in result.feed.entries:
                normalized = normalize_entry(entry, "https://example.com/rss")
                if normalized:
                    normalized_entries.append(normalized)
            
            # All entries should normalize
            assert len(normalized_entries) == 3
            
            # But in a real pipeline, duplicates would be detected:
            # - First two have same URL (same url_sha1)
            # - Would result in only 1 insert for the duplicate URL
            url_sha1_counts = {}
            for entry in normalized_entries:
                sha1 = entry["url_sha1"]
                url_sha1_counts[sha1] = url_sha1_counts.get(sha1, 0) + 1
            
            # Should have 2 unique URLs (one appears twice)
            assert len(url_sha1_counts) == 2
            assert 2 in url_sha1_counts.values()  # One URL appears twice
            assert 1 in url_sha1_counts.values()  # One URL appears once


if __name__ == "__main__":
    pytest.main([__file__, "-v"])