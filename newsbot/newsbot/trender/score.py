"""Sistema de scoring para trending topics.

Implementa métricas compuestas para evaluar y ranking de clusters/topics:
- Viral score: velocidad de crecimiento y engagement
- Freshness score: qué tan reciente es el contenido
- Diversity score: variedad de fuentes y perspectivas
- Volume score: cantidad de contenido relacionado
- Quality score: métricas de calidad del contenido
- Composite score: puntuación final ponderada
"""

import asyncio
import time
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.core.db import AsyncSessionLocal
from newsbot.core.logging import get_logger
from newsbot.core.repositories import (
    get_cluster_with_items,
    get_cluster_stats,
    update_cluster_score
)

logger = get_logger(__name__)

# Scoring configuration
VIRAL_WEIGHT = 0.25
FRESHNESS_WEIGHT = 0.20
DIVERSITY_WEIGHT = 0.20
VOLUME_WEIGHT = 0.15
QUALITY_WEIGHT = 0.20

# Thresholds and parameters
MIN_ITEMS_FOR_SCORING = 3
MAX_HOURS_FOR_FRESHNESS = 48
DIVERSITY_SOURCE_WEIGHT = 0.6
DIVERSITY_DOMAIN_WEIGHT = 0.4


@dataclass
class ClusterMetrics:
    """Métricas calculadas para un cluster."""
    cluster_id: int
    viral_score: float
    freshness_score: float
    diversity_score: float
    volume_score: float
    quality_score: float
    composite_score: float
    item_count: int
    avg_age_hours: float
    unique_sources: int
    unique_domains: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'cluster_id': self.cluster_id,
            'viral_score': self.viral_score,
            'freshness_score': self.freshness_score,
            'diversity_score': self.diversity_score,
            'volume_score': self.volume_score,
            'quality_score': self.quality_score,
            'composite_score': self.composite_score,
            'item_count': self.item_count,
            'avg_age_hours': self.avg_age_hours,
            'unique_sources': self.unique_sources,
            'unique_domains': self.unique_domains
        }


class TrendingScorer:
    """Calculator de scores para trending topics."""
    
    def __init__(self, viral_weight: float = VIRAL_WEIGHT,
                 freshness_weight: float = FRESHNESS_WEIGHT,
                 diversity_weight: float = DIVERSITY_WEIGHT,
                 volume_weight: float = VOLUME_WEIGHT,
                 quality_weight: float = QUALITY_WEIGHT):
        
        self.weights = {
            'viral': viral_weight,
            'freshness': freshness_weight,
            'diversity': diversity_weight,
            'volume': volume_weight,
            'quality': quality_weight
        }
        
        # Normalize weights
        total_weight = sum(self.weights.values())
        for key in self.weights:
            self.weights[key] /= total_weight
    
    def calculate_viral_score(self, items: List[Dict[str, Any]]) -> float:
        """
        Calculate viral score based on velocity and engagement.
        
        Factors:
        - Rate of new items over time (velocity)
        - Acceleration in recent periods
        - Concentration of activity in short periods
        """
        if len(items) < 2:
            return 0.0
        
        now = datetime.now(timezone.utc)
        
        # Sort items by published time
        sorted_items = sorted(items, key=lambda x: x.get('published_at', now))
        
        # Calculate time windows and item counts
        hour_buckets = {}
        
        for item in sorted_items:
            pub_time = item.get('published_at', now)
            if isinstance(pub_time, str):
                try:
                    pub_time = datetime.fromisoformat(pub_time.replace('Z', '+00:00'))
                except:
                    pub_time = now
            
            hours_ago = (now - pub_time).total_seconds() / 3600
            hour_bucket = int(hours_ago)
            
            if hour_bucket not in hour_buckets:
                hour_buckets[hour_bucket] = 0
            hour_buckets[hour_bucket] += 1
        
        if not hour_buckets:
            return 0.0
        
        # Calculate velocity score
        recent_hours = [h for h in hour_buckets.keys() if h <= 6]  # Last 6 hours
        all_hours = list(hour_buckets.keys())
        
        if not recent_hours:
            recent_velocity = 0.0
        else:
            recent_count = sum(hour_buckets[h] for h in recent_hours)
            recent_velocity = recent_count / min(6, max(recent_hours) + 1)
        
        if len(all_hours) <= 6:
            overall_velocity = len(items) / max(1, max(all_hours) + 1)
        else:
            overall_count = sum(hour_buckets[h] for h in all_hours)
            overall_velocity = overall_count / max(1, max(all_hours) + 1)
        
        # Velocity ratio (recent vs overall)
        if overall_velocity > 0:
            velocity_ratio = recent_velocity / overall_velocity
        else:
            velocity_ratio = 1.0
        
        # Apply logarithmic scaling to prevent extreme values
        viral_score = min(1.0, math.log(1 + velocity_ratio) / math.log(10))
        
        return viral_score
    
    def calculate_freshness_score(self, items: List[Dict[str, Any]]) -> float:
        """
        Calculate freshness score based on recency of content.
        
        Factors:
        - Average age of items
        - Percentage of very recent items (< 6 hours)
        - Exponential decay for older content
        """
        if not items:
            return 0.0
        
        now = datetime.now(timezone.utc)
        ages_hours = []
        
        for item in items:
            pub_time = item.get('published_at', now)
            if isinstance(pub_time, str):
                try:
                    pub_time = datetime.fromisoformat(pub_time.replace('Z', '+00:00'))
                except:
                    pub_time = now
            
            age_hours = (now - pub_time).total_seconds() / 3600
            ages_hours.append(max(0, age_hours))
        
        if not ages_hours:
            return 0.0
        
        # Average age score (exponential decay)
        avg_age = sum(ages_hours) / len(ages_hours)
        age_score = math.exp(-avg_age / 12)  # Half-life of 12 hours
        
        # Recent items bonus
        very_recent = sum(1 for age in ages_hours if age <= 6)
        recent_ratio = very_recent / len(ages_hours)
        
        # Combined freshness score
        freshness_score = 0.7 * age_score + 0.3 * recent_ratio
        
        return min(1.0, freshness_score)
    
    def calculate_diversity_score(self, items: List[Dict[str, Any]]) -> float:
        """
        Calculate diversity score based on source and domain variety.
        
        Factors:
        - Number of unique sources
        - Number of unique domains
        - Distribution balance across sources
        """
        if not items:
            return 0.0
        
        sources = set()
        domains = set()
        source_counts = {}
        
        for item in items:
            # Extract source
            source_url = item.get('source_url', '')
            if source_url:
                sources.add(source_url)
                if source_url not in source_counts:
                    source_counts[source_url] = 0
                source_counts[source_url] += 1
            
            # Extract domain from URL
            url = item.get('url', '')
            if url:
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc.lower()
                    if domain:
                        domains.add(domain)
                except:
                    pass
        
        total_items = len(items)
        
        # Source diversity
        unique_sources = len(sources)
        if unique_sources <= 1:
            source_diversity = 0.0
        else:
            # Shannon entropy for source distribution
            entropy = 0.0
            for count in source_counts.values():
                p = count / total_items
                if p > 0:
                    entropy -= p * math.log2(p)
            
            max_entropy = math.log2(unique_sources) if unique_sources > 1 else 1
            source_diversity = entropy / max_entropy if max_entropy > 0 else 0
        
        # Domain diversity
        unique_domains = len(domains)
        domain_diversity = min(1.0, unique_domains / max(1, total_items * 0.5))
        
        # Combined diversity score
        diversity_score = (
            DIVERSITY_SOURCE_WEIGHT * source_diversity +
            DIVERSITY_DOMAIN_WEIGHT * domain_diversity
        )
        
        return min(1.0, diversity_score)
    
    def calculate_volume_score(self, items: List[Dict[str, Any]], 
                             global_stats: Optional[Dict[str, Any]] = None) -> float:
        """
        Calculate volume score based on content quantity.
        
        Factors:
        - Absolute number of items
        - Relative volume compared to other clusters
        - Growth rate over time
        """
        item_count = len(items)
        
        if item_count == 0:
            return 0.0
        
        # Base volume score (logarithmic scaling)
        base_score = math.log(1 + item_count) / math.log(100)  # Max around 100 items
        
        # Relative volume if global stats available
        relative_score = 1.0
        if global_stats and 'avg_cluster_size' in global_stats:
            avg_size = global_stats['avg_cluster_size']
            if avg_size > 0:
                relative_score = min(2.0, item_count / avg_size)
        
        # Combined volume score
        volume_score = min(1.0, 0.7 * base_score + 0.3 * (relative_score / 2.0))
        
        return volume_score
    
    def calculate_quality_score(self, items: List[Dict[str, Any]]) -> float:
        """
        Calculate quality score based on content characteristics.
        
        Factors:
        - Content length and completeness
        - Title quality (length, non-generic)
        - Summary availability and quality
        - URL quality (not redirects/trackers)
        """
        if not items:
            return 0.0
        
        quality_scores = []
        
        for item in items:
            item_quality = 0.0
            
            # Title quality (25%)
            title = item.get('title', '')
            if title:
                title_len = len(title.strip())
                if 10 <= title_len <= 200:  # Reasonable title length
                    title_quality = min(1.0, title_len / 100)
                    
                    # Penalize generic titles
                    generic_words = ['news', 'update', 'breaking', 'latest']
                    if not any(word in title.lower() for word in generic_words):
                        title_quality *= 1.2
                    
                    item_quality += 0.25 * min(1.0, title_quality)
            
            # Summary quality (25%)
            summary = item.get('summary', '')
            if summary:
                summary_len = len(summary.strip())
                if summary_len >= 50:  # Meaningful summary
                    summary_quality = min(1.0, summary_len / 500)
                    item_quality += 0.25 * summary_quality
            
            # Content completeness (25%)
            content = item.get('content', '')
            if content:
                content_len = len(content.strip())
                if content_len >= 100:  # Substantial content
                    content_quality = min(1.0, content_len / 2000)
                    item_quality += 0.25 * content_quality
            
            # URL quality (25%)
            url = item.get('url', '')
            if url:
                url_quality = 1.0
                
                # Penalize tracking/redirect URLs
                bad_patterns = ['redirect', 'track', 'utm_', 'fb_', 'gclid']
                for pattern in bad_patterns:
                    if pattern in url.lower():
                        url_quality *= 0.8
                
                item_quality += 0.25 * url_quality
            
            quality_scores.append(min(1.0, item_quality))
        
        # Average quality across all items
        return sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
    
    def calculate_composite_score(self, viral: float, freshness: float,
                                diversity: float, volume: float, quality: float) -> float:
        """Calculate weighted composite score."""
        
        composite = (
            self.weights['viral'] * viral +
            self.weights['freshness'] * freshness +
            self.weights['diversity'] * diversity +
            self.weights['volume'] * volume +
            self.weights['quality'] * quality
        )
        
        return min(1.0, max(0.0, composite))
    
    def score_cluster(self, cluster_id: int, items: List[Dict[str, Any]],
                     global_stats: Optional[Dict[str, Any]] = None) -> ClusterMetrics:
        """Score a single cluster comprehensively."""
        
        if len(items) < MIN_ITEMS_FOR_SCORING:
            # Return minimal score for small clusters
            return ClusterMetrics(
                cluster_id=cluster_id,
                viral_score=0.0,
                freshness_score=0.0,
                diversity_score=0.0,
                volume_score=0.0,
                quality_score=0.0,
                composite_score=0.0,
                item_count=len(items),
                avg_age_hours=0.0,
                unique_sources=0,
                unique_domains=0
            )
        
        # Calculate individual scores
        viral_score = self.calculate_viral_score(items)
        freshness_score = self.calculate_freshness_score(items)
        diversity_score = self.calculate_diversity_score(items)
        volume_score = self.calculate_volume_score(items, global_stats)
        quality_score = self.calculate_quality_score(items)
        
        # Calculate composite score
        composite_score = self.calculate_composite_score(
            viral_score, freshness_score, diversity_score,
            volume_score, quality_score
        )
        
        # Calculate additional metrics
        now = datetime.now(timezone.utc)
        ages = []
        sources = set()
        domains = set()
        
        for item in items:
            # Age calculation
            pub_time = item.get('published_at', now)
            if isinstance(pub_time, str):
                try:
                    pub_time = datetime.fromisoformat(pub_time.replace('Z', '+00:00'))
                except:
                    pub_time = now
            
            age_hours = (now - pub_time).total_seconds() / 3600
            ages.append(max(0, age_hours))
            
            # Source tracking
            if item.get('source_url'):
                sources.add(item['source_url'])
            
            # Domain tracking
            if item.get('url'):
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(item['url']).netloc.lower()
                    if domain:
                        domains.add(domain)
                except:
                    pass
        
        avg_age_hours = sum(ages) / len(ages) if ages else 0.0
        
        return ClusterMetrics(
            cluster_id=cluster_id,
            viral_score=viral_score,
            freshness_score=freshness_score,
            diversity_score=diversity_score,
            volume_score=volume_score,
            quality_score=quality_score,
            composite_score=composite_score,
            item_count=len(items),
            avg_age_hours=avg_age_hours,
            unique_sources=len(sources),
            unique_domains=len(domains)
        )


async def score_all_clusters(session: AsyncSession,
                           window_hours: int = 24) -> List[ClusterMetrics]:
    """
    Score all active clusters.
    
    Args:
        session: Database session
        window_hours: Time window for cluster analysis
        
    Returns:
        List of scored cluster metrics
    """
    start_time = time.time()
    
    try:
        # Get all clusters with their items
        from newsbot.core.repositories import get_active_clusters
        clusters = await get_active_clusters(session, window_hours)
        
        if not clusters:
            logger.info("No active clusters found for scoring")
            return []
        
        logger.info(f"Scoring {len(clusters)} clusters")
        
        scorer = TrendingScorer()
        scored_clusters = []
        
        # Calculate global stats for relative scoring
        total_items = 0
        for cluster in clusters:
            cluster_with_items = await get_cluster_with_items(session, cluster.id)
            if cluster_with_items:
                total_items += len(cluster_with_items.get('items', []))
        
        avg_cluster_size = total_items / len(clusters) if clusters else 0
        global_stats = {
            'avg_cluster_size': avg_cluster_size,
            'total_clusters': len(clusters),
            'total_items': total_items
        }
        
        # Score each cluster
        for cluster in clusters:
            try:
                cluster_with_items = await get_cluster_with_items(session, cluster.id)
                if not cluster_with_items:
                    continue
                
                items = cluster_with_items.get('items', [])
                if not items:
                    continue
                
                # Score the cluster
                metrics = scorer.score_cluster(cluster.id, items, global_stats)
                scored_clusters.append(metrics)
                
                # Update cluster score in database
                await update_cluster_score(session, cluster.id, metrics.composite_score)
                
                logger.debug(
                    f"Cluster {cluster.id}: {metrics.composite_score:.3f} "
                    f"(viral:{metrics.viral_score:.2f}, fresh:{metrics.freshness_score:.2f}, "
                    f"div:{metrics.diversity_score:.2f}, vol:{metrics.volume_score:.2f}, "
                    f"qual:{metrics.quality_score:.2f})"
                )
                
            except Exception as e:
                logger.error(f"Error scoring cluster {cluster.id}: {e}")
        
        # Sort by composite score
        scored_clusters.sort(key=lambda x: x.composite_score, reverse=True)
        
        runtime = time.time() - start_time
        logger.info(
            f"Scored {len(scored_clusters)} clusters in {runtime:.2f}s, "
            f"top score: {scored_clusters[0].composite_score:.3f}" if scored_clusters else "no clusters"
        )
        
        return scored_clusters
        
    except Exception as e:
        logger.error(f"Cluster scoring failed: {e}")
        return []


async def run_scoring_pipeline(window_hours: int = 24) -> Dict[str, Any]:
    """
    Run complete scoring pipeline.
    
    Args:
        window_hours: Time window for analysis
        
    Returns:
        Scoring statistics and results
    """
    start_time = time.time()
    
    async with AsyncSessionLocal() as session:
        try:
            scored_clusters = await score_all_clusters(session, window_hours)
            
            return {
                'runtime_seconds': time.time() - start_time,
                'clusters_scored': len(scored_clusters),
                'top_scores': [
                    {
                        'cluster_id': cluster.cluster_id,
                        'score': cluster.composite_score,
                        'items': cluster.item_count
                    }
                    for cluster in scored_clusters[:10]
                ],
                'avg_score': sum(c.composite_score for c in scored_clusters) / len(scored_clusters) if scored_clusters else 0,
                'scored_clusters': [c.to_dict() for c in scored_clusters]
            }
            
        except Exception as e:
            logger.error(f"Scoring pipeline failed: {e}")
            return {
                'runtime_seconds': time.time() - start_time,
                'clusters_scored': 0,
                'error': str(e)
            }