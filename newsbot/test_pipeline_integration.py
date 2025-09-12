#!/usr/bin/env python3
"""Test script for pipeline integration with enhanced RSS fetcher."""

import asyncio
import os
import tempfile
import yaml
from pathlib import Path

from newsbot.ingestor.pipeline import run_ingest
from newsbot.core.logging import get_logger

logger = get_logger(__name__)

async def test_pipeline_integration():
    """Test the pipeline with enhanced RSS fetcher integration."""
    
    # Create a temporary config file with a few test feeds
    test_config = {
        'sources': [
            {
                'name': 'BBC News',
                'url': 'https://feeds.bbci.co.uk/news/rss.xml',
                'category': 'news',
                'language': 'en',
                'active': True
            },
            {
                'name': 'Reuters Top News',
                'url': 'https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best',
                'category': 'business', 
                'language': 'en',
                'active': True
            }
        ]
    }
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(test_config, f)
        config_path = f.name
    
    try:
        # Set environment variable for config
        os.environ['NEWSBOT_SOURCES_CONFIG'] = config_path
        
        print("Testing pipeline integration with enhanced RSS fetcher...")
        print("This will test:")
        print("- Pipeline orchestration with bounded concurrency")
        print("- Integration with database (if available)")
        print("- Error handling and statistics")
        print("- SimHash deduplication")
        print()
        
        # Run the ingestion pipeline
        stats = await run_ingest(window_hours=24)
        
        print("Pipeline execution completed!")
        print(f"Statistics: {stats}")
        
    except Exception as e:
        print(f"Pipeline test failed: {e}")
        logger.exception("Pipeline test error")
        
    finally:
        # Cleanup
        try:
            os.unlink(config_path)
        except:
            pass
        
        # Remove environment variable
        if 'NEWSBOT_SOURCES_CONFIG' in os.environ:
            del os.environ['NEWSBOT_SOURCES_CONFIG']

if __name__ == "__main__":
    asyncio.run(test_pipeline_integration())