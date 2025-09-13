"""Database models for NewsBot."""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, Integer, BigInteger,
    ForeignKey, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy.sql import func

from .db import Base


class Source(Base):
    """News sources table."""
    __tablename__ = "sources"
    
    id = mapped_column(Integer, primary_key=True)
    name = mapped_column(String(200), nullable=False)
    type = mapped_column(String(32), nullable=False)  # 'rss' | 'json'
    url = mapped_column(String(1000), unique=True, nullable=False)
    lang = mapped_column(String(8), nullable=True)
    etag = mapped_column(String(200), nullable=True)
    last_modified = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at = mapped_column(DateTime(timezone=True), nullable=True)
    error_count = mapped_column(Integer, default=0, nullable=False)
    active = mapped_column(Boolean, default=True, nullable=False)


class RawItem(Base):
    """Raw items from sources before processing."""
    __tablename__ = "raw_items"
    
    id = mapped_column(BigInteger, primary_key=True)
    source_id = mapped_column(ForeignKey("sources.id"), index=True, nullable=False)
    title = mapped_column(String(800), nullable=False)
    url = mapped_column(String(1500), nullable=False, index=True)
    summary = mapped_column(Text, nullable=True)
    lang = mapped_column(String(8), nullable=True)
    published_at = mapped_column(DateTime(timezone=True), index=True)  # UTC
    fetched_at = mapped_column(DateTime(timezone=True), index=True)
    url_sha1 = mapped_column(String(40), index=True)
    text_simhash = mapped_column(String(32), index=True)  # hex
    payload = mapped_column(JSON, nullable=True)  # raw parsed entry
    
    __table_args__ = (UniqueConstraint("url_sha1", name="uq_raw_urlsha1"),)


class Cluster(Base):
    """Article clusters for grouping related content and trending analysis."""
    __tablename__ = "clusters"
    
    id = mapped_column(Integer, primary_key=True)
    name = mapped_column(String(500), nullable=True)  # Human-readable cluster name
    title = mapped_column(String(500), nullable=True)  # Representative title
    description = mapped_column(Text, nullable=True)  # Combined summary
    keywords = mapped_column(JSON, nullable=True)  # List of keywords
    
    # Trending and scoring fields
    centroid_vector = mapped_column(Text, nullable=True)  # JSON serialized embedding
    composite_score = mapped_column(String(20), nullable=True)  # Float as string for precision
    viral_score = mapped_column(String(20), nullable=True)
    freshness_score = mapped_column(String(20), nullable=True)
    diversity_score = mapped_column(String(20), nullable=True)
    volume_score = mapped_column(String(20), nullable=True)
    quality_score = mapped_column(String(20), nullable=True)
    
    # Metadata
    item_count = mapped_column(Integer, default=0, nullable=False)
    unique_sources = mapped_column(Integer, default=0, nullable=False)
    unique_domains = mapped_column(Integer, default=0, nullable=False)
    avg_age_hours = mapped_column(String(20), nullable=True)  # Float as string
    
    # Timestamps
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = mapped_column(DateTime(timezone=True), onupdate=func.now())
    last_scored_at = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active = mapped_column(Boolean, default=True, nullable=False, index=True)


class ClusterItem(Base):
    """Association between clusters and raw items."""
    __tablename__ = "cluster_items"
    
    id = mapped_column(BigInteger, primary_key=True)
    cluster_id = mapped_column(ForeignKey("clusters.id"), nullable=False, index=True)
    raw_item_id = mapped_column(ForeignKey("raw_items.id"), nullable=False, index=True)
    match_score = mapped_column(String(20), nullable=True)  # How well item matches cluster
    added_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    __table_args__ = (
        UniqueConstraint("cluster_id", "raw_item_id", name="uq_cluster_item"),
        Index('idx_cluster_items_cluster_added', 'cluster_id', 'added_at'),
    )


class Article(Base):
    """Processed articles ready for publication."""
    __tablename__ = "articles"
    
    id = mapped_column(Integer, primary_key=True)
    cluster_id = mapped_column(ForeignKey("clusters.id"), index=True)
    title = mapped_column(String(500), nullable=False)
    content = mapped_column(Text, nullable=False)
    summary = mapped_column(Text)
    keywords = mapped_column(JSON)  # List of keywords
    status = mapped_column(String(50), default="draft", index=True)
    published_at = mapped_column(DateTime(timezone=True), index=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # TODO: Add status enum constraint and publication workflow


class Topic(Base):
    """Topics for content categorization and trending analysis."""
    __tablename__ = "topics"
    
    id = mapped_column(Integer, primary_key=True)
    name = mapped_column(String(255), nullable=False, unique=True, index=True)
    description = mapped_column(Text, nullable=True)
    keywords = mapped_column(JSON, nullable=True)  # List of related keywords
    queries = mapped_column(JSON, nullable=True)  # List of search queries/patterns
    
    # Trending configuration
    cadence_minutes = mapped_column(Integer, default=60, nullable=False)  # How often to analyze
    max_per_run = mapped_column(Integer, default=20, nullable=False)  # Max trends per run
    boost_factor = mapped_column(String(20), default="1.0", nullable=False)  # Score multiplier
    min_score = mapped_column(String(20), default="0.1", nullable=False)  # Minimum relevance score
    
    # Status and metadata
    is_active = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_run_at = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # TODO: Add hierarchical topic relationships


class TopicRun(Base):
    """Topic analysis runs and results."""
    __tablename__ = "topic_runs"
    
    id = mapped_column(Integer, primary_key=True)
    topic_id = mapped_column(ForeignKey("topics.id"), nullable=False, index=True)
    status = mapped_column(String(50), default="pending", index=True)
    results = mapped_column(JSON)  # Analysis results
    error_message = mapped_column(Text)
    started_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = mapped_column(DateTime(timezone=True))
    
    # TODO: Add run scheduling and retry logic


class FailLog(Base):
    """Error and failure logging."""
    __tablename__ = "fail_logs"
    
    id = mapped_column(Integer, primary_key=True)
    service = mapped_column(String(100), nullable=False, index=True)
    operation = mapped_column(String(255), nullable=False, index=True)
    error_type = mapped_column(String(255), index=True)
    error_message = mapped_column(Text)
    stack_trace = mapped_column(Text)
    context = mapped_column(JSON)  # Additional context data
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # TODO: Add error categorization and alerting rules

# Create indexes for performance
Index('idx_raw_items_source_fetched', RawItem.source_id, RawItem.fetched_at)
Index('idx_raw_items_url_sha1', RawItem.url_sha1)
Index('idx_raw_items_simhash', RawItem.text_simhash)
Index('idx_articles_status_created', Article.status, Article.created_at)
Index('idx_topic_runs_status_started', TopicRun.status, TopicRun.started_at)
Index('idx_fail_logs_service_created', FailLog.service, FailLog.created_at)

# Trending-specific indexes
Index('idx_clusters_score_created', Cluster.composite_score, Cluster.created_at)
Index('idx_clusters_active_scored', Cluster.is_active, Cluster.last_scored_at)
Index('idx_cluster_items_cluster_score', ClusterItem.cluster_id, ClusterItem.match_score)
Index('idx_topics_active_lastrun', Topic.is_active, Topic.last_run_at)