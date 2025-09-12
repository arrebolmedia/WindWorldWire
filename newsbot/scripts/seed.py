#!/usr/bin/env python3
"""Database seeding script for NewsBot.

This script connects to the database, creates all tables, and loads
sources from config/sources.yaml using the repository layer.
"""

import asyncio
import sys
from pathlib import Path

import yaml

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from newsbot.core.db import AsyncSessionLocal, create_all
from newsbot.core.repositories import upsert_source_from_yaml, list_active_sources
from newsbot.core.settings import get_settings

settings = get_settings()


async def load_yaml_config(file_path: Path) -> dict:
    """Load YAML configuration file."""
    if not file_path.exists():
        print(f"Warning: {file_path} not found, skipping...")
        return {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            print(f"✅ Loaded config from {file_path}")
            return config
    except Exception as e:
        print(f"❌ Error loading {file_path}: {e}")
        return {}


async def seed_sources_from_yaml(session) -> int:
    """
    Seed sources from config/sources.yaml using repository functions.
    
    Returns count of sources processed.
    """
    print("📰 Loading sources from config/sources.yaml...")
    
    # Load sources configuration
    config_path = project_root / "config" / "sources.yaml"
    config = await load_yaml_config(config_path)
    
    sources_config = config.get('sources', [])
    if not sources_config:
        print("⚠️  No sources found in config/sources.yaml")
        return 0
    
    print(f"📄 Found {len(sources_config)} sources in configuration")
    
    # Process each source
    processed_count = 0
    for source_config in sources_config:
        try:
            source = await upsert_source_from_yaml(session, source_config)
            print(f"  ✅ {source.name} ({source.url})")
            processed_count += 1
        except Exception as e:
            print(f"  ❌ Error processing source {source_config.get('name', 'unknown')}: {e}")
    
    return processed_count


async def get_active_sources_count(session) -> int:
    """Get count of active sources."""
    try:
        sources = await list_active_sources(session)
        return len(sources)
    except Exception as e:
        print(f"❌ Error getting active sources count: {e}")
        return 0


async def print_source_summary(session):
    """Print summary of sources in database."""
    print("\n" + "="*60)
    print("📊 SOURCE SUMMARY")
    print("="*60)
    
    try:
        sources = await list_active_sources(session)
        
        if not sources:
            print("No active sources found in database.")
            return
        
        print(f"Total active sources: {len(sources)}")
        print("\nActive sources:")
        
        for i, source in enumerate(sources, 1):
            status_info = []
            if source.last_checked_at:
                status_info.append(f"last checked: {source.last_checked_at.strftime('%Y-%m-%d %H:%M')}")
            if source.error_count > 0:
                status_info.append(f"errors: {source.error_count}")
            
            status_str = f" ({', '.join(status_info)})" if status_info else ""
            
            print(f"  {i:2d}. {source.name}")
            print(f"      URL: {source.url}")
            print(f"      Language: {source.lang}, Type: {source.type}{status_str}")
        
    except Exception as e:
        print(f"❌ Error getting source summary: {e}")


async def main():
    """Main seeding function."""
    print("🌱 Starting NewsBot database seeding...")
    print(f"📍 Project root: {project_root}")
    
    try:
        # Create all tables
        print("\n📊 Creating database tables...")
        await create_all()
        print("✅ Database tables ready")
        
        # Use async session for operations
        async with AsyncSessionLocal() as session:
            print("🔌 Connected to database")
            
            # Seed sources from YAML
            print("\n📰 Processing sources from YAML configuration...")
            sources_processed = await seed_sources_from_yaml(session)
            
            # Get final count of active sources
            active_count = await get_active_sources_count(session)
            
            # Print summary
            await print_source_summary(session)
        
        # Print final summary
        print("\n" + "="*60)
        print("🎉 DATABASE SEEDING COMPLETE!")
        print("="*60)
        print(f"📰 Sources processed: {sources_processed}")
        print(f"📈 Total active sources: {active_count}")
        print(f"🔗 Database URL: {settings.db_url.replace('postgresql+asyncpg://', 'postgresql://').split('@')[1] if '@' in str(settings.db_url) else 'configured'}")
        print("="*60)
        
        if active_count == 0:
            print("⚠️  No active sources found. Check your config/sources.yaml file.")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"❌ Error during seeding: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)