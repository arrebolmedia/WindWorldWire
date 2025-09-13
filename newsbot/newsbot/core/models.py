"""Database models for NewsBot."""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, Integer, BigInteger,
    ForeignKey, JSON, Index, UniqueConstraint, Float, ARRAY
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
    
    id = mapped_column(BigInteger, primary_key=True)
    centroid = mapped_column(ARRAY(Float), nullable=True)  # embedding medio (opcional)
    topic_key = mapped_column(String(64), nullable=True, index=True)  # si viene de tema dirigido
    first_seen = mapped_column(DateTime(timezone=True), index=True)
    last_seen = mapped_column(DateTime(timezone=True), index=True)
    items_count = mapped_column(Integer, default=0, nullable=False)
    domains_count = mapped_column(Integer, default=0, nullable=False)
    domains = mapped_column(JSON, nullable=True)  # {domain: count}
    score_trend = mapped_column(Float, default=0.0, index=True)
    score_fresh = mapped_column(Float, default=0.0)
    score_diversity = mapped_column(Float, default=0.0)
    score_total = mapped_column(Float, default=0.0, index=True)
    status = mapped_column(String(16), default="open")  # open|picked|stale


class ClusterItem(Base):
    """Association between clusters and raw items."""
    __tablename__ = "cluster_items"
    
    id = mapped_column(BigInteger, primary_key=True)
    cluster_id = mapped_column(ForeignKey("clusters.id"), index=True, nullable=False)
    raw_item_id = mapped_column(ForeignKey("raw_items.id"), index=True, nullable=False)
    source_domain = mapped_column(String(255), index=True)
    similarity = mapped_column(Float, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), index=True)


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
    
    key = mapped_column(String(64), primary_key=True)
    name = mapped_column(String(255), nullable=False)
    priority = mapped_column(Float, default=0.5)
    enabled = mapped_column(Boolean, default=True)
    config = mapped_column(JSON, nullable=True)


class TopicRun(Base):
    """Topic analysis runs and results."""
    __tablename__ = "topic_runs"
    
    id = mapped_column(Integer, primary_key=True)
    topic_key = mapped_column(ForeignKey("topics.key"), nullable=False, index=True)
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

# Índices recomendados para trending
Index('idx_clusters_last_seen_desc', Cluster.last_seen.desc())
Index('idx_clusters_score_total_desc', Cluster.score_total.desc())
Index('idx_cluster_items_source_domain', ClusterItem.source_domain)