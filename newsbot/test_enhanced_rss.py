#!/usr/bin/env python3
"""Test script for enhanced RSS fetcher with concurrency and retry logic."""

import asyncio
import time
from newsbot.ingestor.rss import RSSFetcher
from newsbot.core.logging import get_logger

logger = get_logger(__name__)

async def test_concurrency_and_retry():
    """Test the enhanced RSS fetcher with concurrency controls and retry logic."""
    
    # Test URLs - mix of valid feeds and edge cases
    test_urls = [
        "https://feeds.bbci.co.uk/news/rss.xml",  # BBC News
        "https://rss.cnn.com/rss/edition.rss",    # CNN
        "https://httpstat.us/429",                # Rate limit test
        "https://httpstat.us/503",                # Server error test  
        "https://httpstat.us/200?sleep=2000",     # Slow response test
        "https://invalid-domain-12345.com/feed", # Network error test
    ]
    
    # Create fetcher with low concurrency for testing
    fetcher = RSSFetcher(timeout=5.0, max_retries=2, max_concurrent=3)
    
    print(f"Testing {len(test_urls)} URLs with max_concurrent=3...")
    print("This will test:")
    print("- Concurrency limiting via asyncio.Semaphore")
    print("- Timeout handling (5s timeout)")
    print("- Retry with exponential backoff (0.5, 1, 2s)")
    print("- Rate limiting (HTTP 429) with Retry-After")
    print("- Server error handling (HTTP 5xx)")
    print("- Network error handling")
    print()
    
    start_time = time.time()
    
    # Create tasks for concurrent execution
    tasks = []
    for i, url in enumerate(test_urls):
        task = asyncio.create_task(test_single_url(fetcher, i+1, url))
        tasks.append(task)
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    end_time = time.time()
    
    print(f"\nAll tests completed in {end_time - start_time:.2f} seconds")
    print(f"Results summary:")
    
    success_count = 0
    error_count = 0
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"  URL {i+1}: EXCEPTION - {result}")
            error_count += 1
        elif result and result.status_code == 200:
            print(f"  URL {i+1}: SUCCESS - {len(result.feed.entries) if result.feed else 0} entries")
            success_count += 1
        elif result and result.status_code == 304:
            print(f"  URL {i+1}: NOT MODIFIED (304)")
            success_count += 1
        else:
            print(f"  URL {i+1}: ERROR - {result.error if result else 'No result'}")
            error_count += 1
    
    print(f"\nSummary: {success_count} successful, {error_count} errors")
    
    # Cleanup
    await fetcher.client.aclose()

async def test_single_url(fetcher: RSSFetcher, index: int, url: str):
    """Test a single URL with timing and logging."""
    start_time = time.time()
    
    try:
        print(f"[{index}] Starting: {url}")
        result = await fetcher.fetch(url)
        
        end_time = time.time()
        duration = end_time - start_time
        
        if result.status_code == 200:
            entry_count = len(result.feed.entries) if result.feed else 0
            print(f"[{index}] SUCCESS ({duration:.2f}s): {entry_count} entries from {url}")
        elif result.status_code == 304:
            print(f"[{index}] NOT MODIFIED ({duration:.2f}s): {url}")
        else:
            print(f"[{index}] ERROR ({duration:.2f}s): {result.error} - {url}")
        
        return result
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"[{index}] EXCEPTION ({duration:.2f}s): {e} - {url}")
        raise

if __name__ == "__main__":
    asyncio.run(test_concurrency_and_retry())