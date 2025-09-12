#!/usr/bin/env python3
"""Test script for the RSS ingestion pipeline."""

import asyncio
import sys
from pathlib import Path

# Add the newsbot package to the path
sys.path.insert(0, str(Path(__file__).parent))

from newsbot.ingestor.pipeline import run_ingest, run_cli


async def test_pipeline():
    """Test the pipeline with a small window for quick testing."""
    print("Testing RSS ingestion pipeline...")
    
    # Run with 1 hour window for quick testing
    stats = await run_ingest(window_hours=1)
    
    print("\n=== Pipeline Test Results ===")
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
        for error in stats['errors'][:5]:  # Show first 5 errors
            print(f"  - {error}")
    
    return stats


def test_cli():
    """Test the CLI wrapper."""
    print("Testing CLI wrapper...")
    stats = run_cli(window_hours=1)
    return stats


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test RSS Ingestion Pipeline')
    parser.add_argument(
        '--cli',
        action='store_true',
        help='Test CLI wrapper instead of async function'
    )
    
    args = parser.parse_args()
    
    if args.cli:
        stats = test_cli()
    else:
        stats = asyncio.run(test_pipeline())
    
    # Exit with error code if there were errors
    exit_code = 1 if stats.get('errors') else 0
    sys.exit(exit_code)