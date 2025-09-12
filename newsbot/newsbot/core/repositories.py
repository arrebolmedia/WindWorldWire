"""Repository layer for database operations.

Provides async CRUD operations for sources and idempotent inserts
for raw items with duplicate detection.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy import select, update, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from newsbot.core.models import Source, RawItem
from newsbot.core.logging import get_logger

logger = get_logger(__name__)


async def upsert_source_from_yaml(session: AsyncSession, yaml_rec: Dict[str, Any]) -> Source:
    """
    Upsert a source from YAML record by URL.
    
    Args:
        session: Database session
        yaml_rec: YAML record with source configuration
        
    Returns:
        Source object (existing or newly created)
    """
    url = yaml_rec.get('url')
    if not url:
        raise ValueError("Source record missing required 'url' field")
    
    # Try to find existing source by URL
    stmt = select(Source).where(Source.url == url)
    result = await session.execute(stmt)
    existing_source = result.scalar_one_or_none()
    
    if existing_source:
        # Update existing source with new data
        update_data = {}
        
        for field in ['name', 'type', 'lang', 'active']:
            if field in yaml_rec:
                update_data[field] = yaml_rec[field]
        
        if update_data:
            stmt = (
                update(Source)
                .where(Source.id == existing_source.id)
                .values(**update_data)
            )
            await session.execute(stmt)
            await session.commit()
            
            # Refresh the object to get updated values
            await session.refresh(existing_source)
        
        logger.info(f"Updated existing source: {existing_source.name} ({url})")
        return existing_source
    
    else:
        # Create new source
        source_data = {
            'url': url,
            'name': yaml_rec.get('name', url),
            'type': yaml_rec.get('type', 'rss'),
            'lang': yaml_rec.get('lang', 'en'),
            'active': yaml_rec.get('active', True),
            'error_count': 0,
        }
        
        new_source = Source(**source_data)
        session.add(new_source)
        await session.commit()
        await session.refresh(new_source)
        
        logger.info(f"Created new source: {new_source.name} ({url})")
        return new_source


async def list_active_sources(session: AsyncSession) -> List[Source]:
    """
    Get list of all active sources.
    
    Args:
        session: Database session
        
    Returns:
        List of active Source objects
    """
    stmt = select(Source).where(Source.active == True).order_by(Source.name)
    result = await session.execute(stmt)
    sources = result.scalars().all()
    
    logger.debug(f"Retrieved {len(sources)} active sources")
    return list(sources)


async def update_source_headers(
    session: AsyncSession,
    source: Source,
    etag: Optional[str],
    last_modified: Optional[datetime],
    checked_at: Optional[datetime] = None
) -> None:
    """
    Update source caching headers and check timestamp.
    
    Args:
        session: Database session
        source: Source object to update
        etag: ETag header value
        last_modified: Last-Modified header value
        checked_at: When the source was checked (defaults to now)
    """
    if checked_at is None:
        checked_at = datetime.now(timezone.utc)
    
    update_data = {
        'last_checked_at': checked_at,
    }
    
    if etag is not None:
        update_data['etag'] = etag
    
    if last_modified is not None:
        update_data['last_modified'] = last_modified
    
    # Reset error count on successful check
    update_data['error_count'] = 0
    
    stmt = (
        update(Source)
        .where(Source.id == source.id)
        .values(**update_data)
    )
    
    await session.execute(stmt)
    await session.commit()
    
    logger.debug(f"Updated headers for source {source.id}: etag={etag}, last_modified={last_modified}")


async def insert_raw_item_if_new(
    session: AsyncSession,
    source_id: int,
    normalized: Dict[str, Any]
) -> Tuple[bool, RawItem]:
    """
    Insert raw item if new (check by url_sha1).
    
    Args:
        session: Database session
        source_id: Source ID
        normalized: Normalized entry dictionary
        
    Returns:
        Tuple of (was_created: bool, raw_item: RawItem)
        - (False, existing_item) if item already exists
        - (True, new_item) if item was created
    """
    url_sha1 = normalized.get('url_sha1')
    if not url_sha1:
        raise ValueError("Normalized entry missing url_sha1")
    
    # Check if item already exists
    stmt = select(RawItem).where(RawItem.url_sha1 == url_sha1)
    result = await session.execute(stmt)
    existing_item = result.scalar_one_or_none()
    
    if existing_item:
        logger.debug(f"Raw item already exists with url_sha1: {url_sha1[:8]}...")
        return False, existing_item
    
    # Create new raw item
    raw_item_data = {
        'source_id': source_id,
        'title': normalized.get('title', ''),
        'url': normalized.get('url', ''),
        'summary': normalized.get('summary'),
        'lang': normalized.get('lang'),
        'published_at': normalized.get('published_at'),
        'fetched_at': normalized.get('fetched_at'),
        'url_sha1': url_sha1,
        'text_simhash': normalized.get('text_simhash'),
        'payload': normalized.get('payload', {}),
    }
    
    new_item = RawItem(**raw_item_data)
    session.add(new_item)
    
    try:
        await session.commit()
        await session.refresh(new_item)
        
        logger.debug(
            f"Created new raw item: {new_item.id}",
            extra={
                'source_id': source_id,
                'url_sha1': url_sha1[:8] + '...',
                'title': normalized.get('title', '')[:50] + '...'
            }
        )
        
        return True, new_item
        
    except Exception as e:
        await session.rollback()
        
        # Check if it was a race condition (another process inserted the same item)
        stmt = select(RawItem).where(RawItem.url_sha1 == url_sha1)
        result = await session.execute(stmt)
        existing_item = result.scalar_one_or_none()
        
        if existing_item:
            logger.debug(f"Race condition: item was inserted by another process: {url_sha1[:8]}...")
            return False, existing_item
        else:
            # Re-raise the original exception
            logger.error(f"Failed to insert raw item: {e}")
            raise


async def recent_simhashes(session: AsyncSession, window_hours: int = 24) -> List[str]:
    """
    Get recent SimHashes for deduplication window.
    
    Args:
        session: Database session
        window_hours: How many hours back to look
        
    Returns:
        List of SimHash strings from recent items
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    
    stmt = (
        select(RawItem.text_simhash)
        .where(RawItem.fetched_at >= cutoff_time)
        .where(RawItem.text_simhash.isnot(None))
        .distinct()
    )
    
    result = await session.execute(stmt)
    simhashes = [row[0] for row in result.fetchall()]
    
    logger.debug(f"Retrieved {len(simhashes)} unique SimHashes from last {window_hours} hours")
    return simhashes


async def increment_source_error_count(
    session: AsyncSession,
    source: Source,
    error_message: Optional[str] = None
) -> int:
    """
    Increment source error count and update check timestamp.
    
    Args:
        session: Database session
        source: Source object to update
        error_message: Optional error message for logging
        
    Returns:
        New error count
    """
    new_count = source.error_count + 1
    checked_at = datetime.now(timezone.utc)
    
    stmt = (
        update(Source)
        .where(Source.id == source.id)
        .values(
            error_count=new_count,
            last_checked_at=checked_at
        )
    )
    
    await session.execute(stmt)
    await session.commit()
    
    logger.warning(
        f"Incremented error count for source {source.id} to {new_count}",
        extra={'source_url': source.url, 'error_message': error_message}
    )
    
    return new_count


async def batch_insert_raw_items(
    session: AsyncSession,
    source_id: int,
    normalized_entries: List[Dict[str, Any]]
) -> Tuple[int, int]:
    """
    Batch insert raw items with duplicate checking.
    
    Args:
        session: Database session
        source_id: Source ID
        normalized_entries: List of normalized entry dictionaries
        
    Returns:
        Tuple of (created_count, duplicate_count)
    """
    if not normalized_entries:
        return 0, 0
    
    created_count = 0
    duplicate_count = 0
    
    # Extract all url_sha1 values for batch duplicate check
    url_sha1_values = [entry.get('url_sha1') for entry in normalized_entries]
    url_sha1_values = [sha1 for sha1 in url_sha1_values if sha1]
    
    # Get existing url_sha1 values
    stmt = select(RawItem.url_sha1).where(RawItem.url_sha1.in_(url_sha1_values))
    result = await session.execute(stmt)
    existing_sha1s = {row[0] for row in result.fetchall()}
    
    # Filter out duplicates
    new_entries = []
    for entry in normalized_entries:
        url_sha1 = entry.get('url_sha1')
        if url_sha1 and url_sha1 in existing_sha1s:
            duplicate_count += 1
            logger.debug(f"Skipping duplicate entry: {url_sha1[:8]}...")
        else:
            raw_item_data = {
                'source_id': source_id,
                'title': entry.get('title', ''),
                'url': entry.get('url', ''),
                'summary': entry.get('summary'),
                'lang': entry.get('lang'),
                'published_at': entry.get('published_at'),
                'fetched_at': entry.get('fetched_at'),
                'url_sha1': url_sha1,
                'text_simhash': entry.get('text_simhash'),
                'payload': entry.get('payload', {}),
            }
            new_entries.append(raw_item_data)
    
    # Batch insert new entries
    if new_entries:
        try:
            # Use PostgreSQL UPSERT if available
            try:
                stmt = pg_insert(RawItem).values(new_entries)
                stmt = stmt.on_conflict_do_nothing(index_elements=['url_sha1'])
                await session.execute(stmt)
                created_count = len(new_entries)
            except Exception:
                # Fallback to individual inserts
                for entry_data in new_entries:
                    new_item = RawItem(**entry_data)
                    session.add(new_item)
                created_count = len(new_entries)
            
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Batch insert failed: {e}")
            raise
    
    logger.info(
        f"Batch insert completed: {created_count} created, {duplicate_count} duplicates",
        extra={'source_id': source_id}
    )
    
    return created_count, duplicate_count


async def get_source_by_url(session: AsyncSession, url: str) -> Optional[Source]:
    """
    Get source by URL.
    
    Args:
        session: Database session
        url: Source URL
        
    Returns:
        Source object or None if not found
    """
    stmt = select(Source).where(Source.url == url)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_source_stats(session: AsyncSession, source_id: int) -> Dict[str, Any]:
    """
    Get statistics for a source.
    
    Args:
        session: Database session
        source_id: Source ID
        
    Returns:
        Dictionary with source statistics
    """
    # Total items count
    total_stmt = select(func.count(RawItem.id)).where(RawItem.source_id == source_id)
    total_result = await session.execute(total_stmt)
    total_items = total_result.scalar()
    
    # Recent items (last 24 hours)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_stmt = (
        select(func.count(RawItem.id))
        .where(RawItem.source_id == source_id)
        .where(RawItem.fetched_at >= cutoff_time)
    )
    recent_result = await session.execute(recent_stmt)
    recent_items = recent_result.scalar()
    
    # Last fetch time
    last_fetch_stmt = (
        select(func.max(RawItem.fetched_at))
        .where(RawItem.source_id == source_id)
    )
    last_fetch_result = await session.execute(last_fetch_stmt)
    last_fetch = last_fetch_result.scalar()
    
    return {
        'total_items': total_items or 0,
        'recent_items_24h': recent_items or 0,
        'last_fetch_at': last_fetch,
    }


async def cleanup_old_raw_items(
    session: AsyncSession,
    days_to_keep: int = 30
) -> int:
    """
    Clean up old raw items to manage database size.
    
    Args:
        session: Database session
        days_to_keep: Number of days to retain
        
    Returns:
        Number of items deleted
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
    
    # Count items to be deleted
    count_stmt = select(func.count(RawItem.id)).where(RawItem.fetched_at < cutoff_time)
    count_result = await session.execute(count_stmt)
    items_to_delete = count_result.scalar() or 0
    
    if items_to_delete > 0:
        # Delete old items
        delete_stmt = delete(RawItem).where(RawItem.fetched_at < cutoff_time)
        await session.execute(delete_stmt)
        await session.commit()
        
        logger.info(f"Cleaned up {items_to_delete} raw items older than {days_to_keep} days")
    
    return items_to_delete