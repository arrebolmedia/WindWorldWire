#!/usr/bin/env python3
"""Test the database seeding functionality."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from newsbot.core.db import get_async_session
from newsbot.core.repositories import list_active_sources


async def test_sources():
    """Test listing sources from database."""
    print("🔍 Testing source listing...")
    
    try:
        async with get_async_session() as session:
            sources = await list_active_sources(session)
            
            print(f"\n📊 Found {len(sources)} active sources:")
            
            if sources:
                for i, source in enumerate(sources, 1):
                    print(f"  {i:2d}. {source.name}")
                    print(f"      URL: {source.url}")
                    print(f"      Language: {source.lang}")
                    print(f"      Type: {source.type}")
                    print(f"      Active: {source.active}")
                    if source.last_checked_at:
                        print(f"      Last checked: {source.last_checked_at}")
                    if source.error_count > 0:
                        print(f"      Error count: {source.error_count}")
                    print()
            else:
                print("  No sources found. Run the seed script first:")
                print("    python scripts/seed.py")
            
            return len(sources)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return 0


async def main():
    """Main test function."""
    print("🧪 Testing NewsBot Database")
    print("=" * 40)
    
    count = await test_sources()
    
    print("=" * 40)
    print(f"✅ Test completed. Found {count} active sources.")
    
    return 0 if count > 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)