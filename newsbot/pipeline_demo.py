#!/usr/bin/env python3
"""
Integration example: RSS Fetcher + Normalizer Pipeline

This example shows how to use the enhanced RSS fetcher with
the normalization helpers for a complete ingestion pipeline.
"""

import asyncio
from datetime import datetime
from types import SimpleNamespace

from newsbot.ingestor.rss import RSSFetcher
from newsbot.ingestor.normalizer import (
    normalize_entry,
    validate_normalized_entry,
    batch_normalize_entries
)


class IngestionStats:
    """Track ingestion statistics."""
    
    def __init__(self):
        self.sources_processed = 0
        self.sources_failed = 0
        self.entries_fetched = 0
        self.entries_normalized = 0
        self.entries_invalid = 0
        self.cache_hits = 0
        self.start_time = datetime.now()
    
    def __str__(self):
        duration = datetime.now() - self.start_time
        return f"""
Ingestion Statistics:
  Duration: {duration.total_seconds():.2f}s
  Sources processed: {self.sources_processed}
  Sources failed: {self.sources_failed}
  Entries fetched: {self.entries_fetched}
  Entries normalized: {self.entries_normalized}
  Entries invalid: {self.entries_invalid}
  Cache hits: {self.cache_hits}
  Success rate: {self.entries_normalized / max(1, self.entries_fetched) * 100:.1f}%
"""


async def ingest_source(source, fetcher: RSSFetcher, stats: IngestionStats):
    """
    Ingest a single RSS source with normalization.
    
    Args:
        source: Source object with URL and metadata
        fetcher: RSSFetcher instance
        stats: Statistics tracker
        
    Returns:
        List of normalized entries or None if failed
    """
    print(f"📡 Processing: {source.name}")
    print(f"   URL: {source.url}")
    
    try:
        # Fetch RSS feed
        result = await fetcher.fetch_and_parse(source)
        stats.sources_processed += 1
        
        if result.status == "not_modified":
            print("   ✅ 304 Not Modified - using cached content")
            stats.cache_hits += 1
            return []
        
        elif result.status == "error":
            print(f"   ❌ Error: {result.error}")
            stats.sources_failed += 1
            return None
        
        # Update source with caching metadata
        source.etag = result.etag
        source.last_modified = result.last_modified
        
        print(f"   📄 Fetched {len(result.entries)} entries")
        stats.entries_fetched += len(result.entries)
        
        # Normalize entries
        normalized_entries = batch_normalize_entries(result.entries, source)
        stats.entries_normalized += len(normalized_entries)
        stats.entries_invalid += len(result.entries) - len(normalized_entries)
        
        print(f"   ✅ Normalized {len(normalized_entries)} entries")
        
        # Show sample normalized entry
        if normalized_entries:
            entry = normalized_entries[0]
            print(f"   📝 Sample: {entry['title'][:50]}...")
            print(f"      Language: {entry['lang']}")
            print(f"      SimHash: {entry['text_simhash'][:8]}...")
        
        return normalized_entries
        
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        stats.sources_failed += 1
        return None


async def create_mock_sources():
    """Create mock sources for testing."""
    sources = []
    
    # BBC News (reliable RSS)
    bbc = SimpleNamespace()
    bbc.id = 1
    bbc.name = "BBC News"
    bbc.url = "http://feeds.bbci.co.uk/news/rss.xml"
    bbc.type = "rss"
    bbc.lang = "en"
    bbc.etag = None
    bbc.last_modified = None
    bbc.error_count = 0
    sources.append(bbc)
    
    # NPR News (another reliable RSS)
    npr = SimpleNamespace()
    npr.id = 2
    npr.name = "NPR News"
    npr.url = "https://feeds.npr.org/1001/rss.xml"
    npr.type = "rss"
    npr.lang = "en"
    npr.etag = None
    npr.last_modified = None
    npr.error_count = 0
    sources.append(npr)
    
    # Example with cached data
    cached = SimpleNamespace()
    cached.id = 3
    cached.name = "BBC with ETag"
    cached.url = "http://feeds.bbci.co.uk/news/rss.xml"
    cached.type = "rss"
    cached.lang = "en"
    cached.etag = '"cached-etag-123"'  # Simulate cached ETag
    cached.last_modified = None
    cached.error_count = 0
    sources.append(cached)
    
    return sources


async def simulate_database_storage(normalized_entries, source):
    """
    Simulate storing normalized entries in database.
    
    In a real implementation, this would:
    1. Check for duplicates using url_sha1
    2. Check for near-duplicates using text_simhash
    3. Insert new entries into database
    4. Update source metadata (etag, last_modified, error_count)
    """
    print(f"   💾 Simulating database storage for {len(normalized_entries)} entries")
    
    # Simulate duplicate detection
    seen_urls = set()
    duplicates = 0
    
    for entry in normalized_entries:
        if entry['url_sha1'] in seen_urls:
            duplicates += 1
        else:
            seen_urls.add(entry['url_sha1'])
    
    new_entries = len(normalized_entries) - duplicates
    print(f"      New entries: {new_entries}")
    print(f"      Duplicates skipped: {duplicates}")
    
    # In real implementation, would update source in database:
    # UPDATE sources SET etag = ?, last_modified = ?, error_count = 0 WHERE id = ?
    
    return new_entries


async def run_ingestion_pipeline():
    """Run complete RSS ingestion pipeline with normalization."""
    print("🚀 RSS Ingestion Pipeline with Normalization")
    print("=" * 60)
    
    stats = IngestionStats()
    sources = await create_mock_sources()
    
    print(f"📋 Processing {len(sources)} RSS sources:")
    for source in sources:
        print(f"   • {source.name}")
    print()
    
    async with RSSFetcher(timeout=15) as fetcher:
        all_normalized_entries = []
        
        for source in sources:
            print("-" * 50)
            
            # Ingest source
            normalized_entries = await ingest_source(source, fetcher, stats)
            
            if normalized_entries is not None:
                # Simulate database storage
                if normalized_entries:
                    await simulate_database_storage(normalized_entries, source)
                    all_normalized_entries.extend(normalized_entries)
                
                # Show conditional headers for next fetch
                headers = fetcher.get_conditional_headers(source)
                if headers:
                    print(f"   🏷️ Next fetch will use: {list(headers.keys())}")
            
            print()
    
    print("=" * 60)
    print("📊 Pipeline Completed!")
    print(stats)
    
    # Show summary of normalized data
    if all_normalized_entries:
        print(f"🎯 Successfully processed {len(all_normalized_entries)} total entries")
        
        # Language distribution
        languages = {}
        for entry in all_normalized_entries:
            lang = entry.get('lang', 'unknown')
            languages[lang] = languages.get(lang, 0) + 1
        
        print(f"📈 Language distribution: {languages}")
        
        # Show some normalized entries
        print(f"\n📝 Sample normalized entries:")
        for i, entry in enumerate(all_normalized_entries[:3]):
            print(f"   {i+1}. {entry['title'][:60]}...")
            print(f"      URL: {entry['url'][:60]}...")
            print(f"      Published: {entry['published_at']}")
            print(f"      Lang: {entry['lang']}, SimHash: {entry['text_simhash'][:8]}...")
            print()


async def test_individual_functions():
    """Test individual normalizer functions."""
    print("🔧 Testing Individual Normalizer Functions")
    print("-" * 50)
    
    from newsbot.ingestor.normalizer import (
        clean_text, 
        detect_lang, 
        sha1_url, 
        compute_simhash
    )
    
    # Test with real RSS entry
    source = SimpleNamespace()
    source.url = "http://feeds.bbci.co.uk/news/rss.xml"
    source.lang = "en"
    source.etag = None
    source.last_modified = None
    
    async with RSSFetcher() as fetcher:
        result = await fetcher.fetch_and_parse(source)
        
        if result.entries:
            entry = result.entries[0]
            print(f"🔍 Analyzing entry: {entry.get('title', 'No title')[:50]}...")
            
            # Test individual functions
            title_clean = clean_text(entry.get('title', ''))
            print(f"   Clean title: {title_clean[:50]}...")
            
            lang = detect_lang(title_clean)
            print(f"   Detected language: {lang}")
            
            url_hash = sha1_url(entry.get('link', ''))
            print(f"   URL SHA1: {url_hash[:16]}...")
            
            content = f"{title_clean} {clean_text(entry.get('summary', ''))}"
            simhash = compute_simhash(content)
            print(f"   Content SimHash: {simhash[:16]}...")
            
            # Test normalization
            normalized = normalize_entry(entry, source)
            is_valid = validate_normalized_entry(normalized)
            print(f"   Normalization: {'✅ Valid' if is_valid else '❌ Invalid'}")


if __name__ == "__main__":
    print("Note: This requires internet connection for RSS feeds")
    print()
    
    async def main():
        await test_individual_functions()
        print("\n" + "=" * 60)
        await run_ingestion_pipeline()
    
    asyncio.run(main())