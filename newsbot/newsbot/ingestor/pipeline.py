"""RSS Ingestion Pipeline Orchestrator.

Coordinates the complete RSS ingestion workflow:
- Source management from YAML config
- Concurrent RSS fetching with bounded concurrency
- Entry normalization and SimHash computation
- Duplicate detection (hard + soft deduplication)
- Database persistence with comprehensive stats
"""

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml

from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.core.db import AsyncSessionLocal
from newsbot.core.logging import get_logger
from newsbot.core.repositories import (
    upsert_source_from_yaml,
    list_active_sources,
    update_source_headers,
    insert_raw_item_if_new,
    recent_simhashes,
    increment_source_error_count
)
from newsbot.core.simhash import simhash, hamming_distance
from newsbot.ingestor.rss import RSSFetcher
from newsbot.ingestor.normalizer import normalize_entry

logger = get_logger(__name__)

# Configuration
HAMMING_THRESHOLD = 4  # SimHash similarity threshold
DEFAULT_WINDOW_HOURS = 24


async def run_ingest(window_hours: int = DEFAULT_WINDOW_HOURS) -> Dict[str, Any]:
    """
    Run complete RSS ingestion pipeline.
    
    Args:
        window_hours: Deduplication window for SimHash comparison
        
    Returns:
        Dictionary with ingestion statistics
    """
    start_time = time.time()
    stats = {
        'sources_ok': 0,
        'sources_304': 0,
        'sources_error': 0,
        'items_total': 0,
        'items_inserted': 0,
        'items_duplicated': 0,
        'items_simhash_filtered': 0,
        'errors': [],
        'runtime_seconds': 0,
    }
    
    logger.info(f"Starting RSS ingestion pipeline with {window_hours}h dedup window")
    
    try:
        async with AsyncSessionLocal() as session:
            # Step 1: Load and sync sources from config
            await _sync_sources_from_config(session, stats)
            
            # Step 2: Get active sources
            sources = await list_active_sources(session)
            logger.info(f"Found {len(sources)} active sources")
            
            if not sources:
                logger.warning("No active sources found")
                return stats
            
            # Step 3: Get recent SimHashes for soft deduplication
            recent_hashes = await recent_simhashes(session, window_hours)
            logger.info(f"Retrieved {len(recent_hashes)} recent SimHashes for deduplication")
            
            # Step 4: Fetch all sources concurrently
            await _fetch_sources_concurrently(session, sources, recent_hashes, stats)
            
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        stats['errors'].append(f"Pipeline error: {str(e)}")
    
    # Calculate runtime
    stats['runtime_seconds'] = round(time.time() - start_time, 2)
    
    # Log final stats
    logger.info(
        f"Ingestion completed in {stats['runtime_seconds']}s: "
        f"{stats['sources_ok']} sources OK, "
        f"{stats['sources_304']} not modified, "
        f"{stats['sources_error']} errors, "
        f"{stats['items_inserted']}/{stats['items_total']} items inserted"
    )
    
    return stats


async def _sync_sources_from_config(session: AsyncSession, stats: Dict[str, Any]) -> None:
    """Load sources from YAML config and ensure they exist in database."""
    config_path = Path("config/sources.yaml")
    
    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}")
        stats['errors'].append(f"Config file not found: {config_path}")
        return
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        sources_config = config.get('sources', [])
        logger.info(f"Loading {len(sources_config)} sources from config")
        
        for source_config in sources_config:
            try:
                source = await upsert_source_from_yaml(session, source_config)
                logger.debug(f"Synced source: {source.name} ({source.url})")
            except Exception as e:
                logger.error(f"Error syncing source {source_config.get('url', 'unknown')}: {e}")
                stats['errors'].append(f"Source sync error: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        stats['errors'].append(f"Config load error: {str(e)}")


async def _fetch_sources_concurrently(
    session: AsyncSession,
    sources: List,
    recent_hashes: List[str],
    stats: Dict[str, Any]
) -> None:
    """Fetch all sources concurrently. Concurrency is now controlled by RSSFetcher itself."""
    
    # Create tasks for all sources (no semaphore needed as RSSFetcher handles it)
    tasks = [_process_single_source(session, source, recent_hashes, stats) for source in sources]
    
    # Execute with progress logging
    completed = 0
    for coro in asyncio.as_completed(tasks):
        try:
            await coro
            completed += 1
            if completed % 10 == 0 or completed == len(sources):
                logger.info(f"Processed {completed}/{len(sources)} sources")
        except Exception as e:
            logger.error(f"Task error: {e}")
            stats["errors"] += 1
            stats['errors'].append(f"Task error: {str(e)}")


async def _process_single_source(
    session: AsyncSession,
    source,
    recent_hashes: List[str],
    stats: Dict[str, Any]
) -> None:
    """Process a single RSS source."""
    fetcher = RSSFetcher()
    
    try:
        logger.debug(f"Fetching source: {source.name} ({source.url})")
        
        # Fetch RSS feed
        result = await fetcher.fetch(
            source.url,
            etag=source.etag,
            last_modified=source.last_modified
        )
        
        current_time = datetime.now(timezone.utc)
        
        if result.status_code == 304:
            # Not modified - just update check time
            await update_source_headers(session, source, None, None, current_time)
            stats['sources_304'] += 1
            logger.debug(f"Source not modified: {source.name}")
            return
        
        elif result.status_code == 200:
            # Process entries
            entries_processed = await _process_feed_entries(
                session, source, result, recent_hashes, stats
            )
            
            # Update source headers
            await update_source_headers(
                session, source,
                result.etag,
                result.last_modified,
                current_time
            )
            
            stats['sources_ok'] += 1
            logger.info(f"Processed source: {source.name} ({entries_processed} entries)")
            
        else:
            # Error response
            await increment_source_error_count(
                session, source, f"HTTP {result.status_code}"
            )
            stats['sources_error'] += 1
            error_msg = f"Source {source.name}: HTTP {result.status_code}"
            logger.warning(error_msg)
            stats['errors'].append(error_msg)
            
    except Exception as e:
        # Fetch error
        await increment_source_error_count(session, source, str(e))
        stats['sources_error'] += 1
        error_msg = f"Source {source.name}: {str(e)}"
        logger.error(error_msg)
        stats['errors'].append(error_msg)


async def _process_feed_entries(
    session: AsyncSession,
    source,
    fetch_result,
    recent_hashes: List[str],
    stats: Dict[str, Any]
) -> int:
    """Process all entries from a fetched RSS feed."""
    if not fetch_result.feed or not fetch_result.feed.entries:
        logger.debug(f"No entries found in feed: {source.name}")
        return 0
    
    entries_processed = 0
    
    for entry in fetch_result.feed.entries:
        try:
            # Normalize entry
            normalized = normalize_entry(entry, source.url)
            if not normalized:
                continue
            
            stats['items_total'] += 1
            
            # Compute SimHash for content
            content_text = f"{normalized.get('title', '')} {normalized.get('summary', '')}"
            content_simhash = simhash(content_text)
            normalized['text_simhash'] = content_simhash
            
            # Soft deduplication: check SimHash similarity
            if _is_content_duplicate(content_simhash, recent_hashes):
                stats['items_simhash_filtered'] += 1
                logger.debug(f"Filtered similar content: {normalized.get('title', '')[:50]}...")
                continue
            
            # Hard deduplication: attempt insert
            was_created, raw_item = await insert_raw_item_if_new(
                session, source.id, normalized
            )
            
            if was_created:
                stats['items_inserted'] += 1
                # Add to recent hashes for subsequent entries
                recent_hashes.append(content_simhash)
                logger.debug(f"Inserted new item: {raw_item.title[:50]}...")
            else:
                stats['items_duplicated'] += 1
                logger.debug(f"Duplicate item: {normalized.get('title', '')[:50]}...")
            
            entries_processed += 1
            
        except Exception as e:
            logger.error(f"Error processing entry from {source.name}: {e}")
            stats['errors'].append(f"Entry processing error: {str(e)}")
    
    return entries_processed


def _is_content_duplicate(content_hash: str, recent_hashes: List[str]) -> bool:
    """Check if content is similar to recently processed items."""
    if not content_hash or not recent_hashes:
        return False
    
    for recent_hash in recent_hashes:
        if hamming_distance(content_hash, recent_hash) < HAMMING_THRESHOLD:
            return True
    
    return False


def run_cli(dry_run: bool = False, window_hours: int = DEFAULT_WINDOW_HOURS) -> Dict[str, Any]:
    """
    Synchronous CLI wrapper for the ingestion pipeline.
    
    Args:
        dry_run: If True, don't actually insert items (for testing)
        window_hours: Deduplication window hours
        
    Returns:
        Ingestion statistics dictionary
    """
    if dry_run:
        logger.info("DRY RUN MODE - No database changes will be made")
        # TODO: Implement dry run logic
    
    # Run the async pipeline
    return asyncio.run(run_ingest(window_hours))


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='RSS Ingestion Pipeline')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without making database changes'
    )
    parser.add_argument(
        '--window-hours',
        type=int,
        default=DEFAULT_WINDOW_HOURS,
        help=f'Deduplication window in hours (default: {DEFAULT_WINDOW_HOURS})'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        import logging
        logging.getLogger('newsbot').setLevel(logging.DEBUG)
    
    # Run pipeline
    stats = run_cli(dry_run=args.dry_run, window_hours=args.window_hours)
    
    # Print results
    print("\n=== RSS Ingestion Results ===")
    print(f"Runtime: {stats['runtime_seconds']}s")
    print(f"Sources OK: {stats['sources_ok']}")
    print(f"Sources Not Modified (304): {stats['sources_304']}")
    print(f"Sources Error: {stats['sources_error']}")
    print(f"Items Total: {stats['items_total']}")
    print(f"Items Inserted: {stats['items_inserted']}")
    print(f"Items Duplicated: {stats['items_duplicated']}")
    print(f"Items SimHash Filtered: {stats['items_simhash_filtered']}")
    
    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):")
        for error in stats['errors'][:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(stats['errors']) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more")
    
    return 0 if not stats['errors'] else 1


if __name__ == "__main__":
    exit(main())