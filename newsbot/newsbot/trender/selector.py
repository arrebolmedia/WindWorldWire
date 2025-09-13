"""Selector de top-K trending topics.

Implementa selección inteligente de las mejores tendencias:
- Top-K global basado en composite scores
- Top-K por tema específico
- Diversidad en la selección (evitar saturación de un solo tema)
- Filtros de calidad y relevancia
- Ranking final con adjustes contextuales
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.core.db import AsyncSessionLocal
from newsbot.core.logging import get_logger
from newsbot.trender.score import ClusterMetrics

logger = get_logger(__name__)

# Selection configuration
DEFAULT_TOP_K = 50
MIN_SCORE_THRESHOLD = 0.1
MAX_SAME_DOMAIN_RATIO = 0.3  # Max 30% from same domain
MAX_SAME_SOURCE_RATIO = 0.4  # Max 40% from same source
DIVERSITY_PENALTY_FACTOR = 0.1
FRESHNESS_BOOST_HOURS = 6


@dataclass
class SelectedTrend:
    """Trending topic seleccionado."""
    cluster_id: int
    rank: int
    score: float
    adjusted_score: float
    title: str
    summary: str
    item_count: int
    unique_sources: int
    avg_age_hours: float
    topic_category: Optional[str] = None
    representative_items: List[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'cluster_id': self.cluster_id,
            'rank': self.rank,
            'score': self.score,
            'adjusted_score': self.adjusted_score,
            'title': self.title,
            'summary': self.summary,
            'item_count': self.item_count,
            'unique_sources': self.unique_sources,
            'avg_age_hours': self.avg_age_hours,
            'topic_category': self.topic_category,
            'representative_items': self.representative_items or []
        }


class TrendingSelector:
    """Selector inteligente de trending topics."""
    
    def __init__(self, min_score: float = MIN_SCORE_THRESHOLD,
                 max_same_domain: float = MAX_SAME_DOMAIN_RATIO,
                 max_same_source: float = MAX_SAME_SOURCE_RATIO):
        
        self.min_score = min_score
        self.max_same_domain = max_same_domain
        self.max_same_source = max_same_source
    
    def extract_cluster_info(self, cluster_data: Dict[str, Any]) -> Tuple[str, str, List[str]]:
        """
        Extract title, summary, and domains from cluster items.
        
        Returns:
            (best_title, combined_summary, domains)
        """
        items = cluster_data.get('items', [])
        if not items:
            return "", "", []
        
        # Find best title (longest, most informative)
        titles = []
        summaries = []
        domains = set()
        
        for item in items:
            if item.get('title'):
                titles.append(item['title'])
            if item.get('summary'):
                summaries.append(item['summary'])
            
            # Extract domain
            url = item.get('url', '')
            if url:
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc.lower()
                    if domain:
                        domains.add(domain)
                except:
                    pass
        
        # Select best title
        if titles:
            # Prefer longer, more specific titles
            best_title = max(titles, key=lambda t: (
                len(t.strip()),
                -t.lower().count('breaking'),  # Prefer non-breaking news
                -t.lower().count('update')     # Prefer non-update titles
            ))
        else:
            best_title = f"Trending Topic (Cluster {cluster_data.get('cluster_id', 'Unknown')})"
        
        # Combine summaries
        if summaries:
            # Take the longest, most informative summary
            best_summary = max(summaries, key=len)
            # Truncate if too long
            if len(best_summary) > 300:
                best_summary = best_summary[:297] + "..."
        else:
            best_summary = "Multiple related articles trending"
        
        return best_title, best_summary, list(domains)
    
    def calculate_diversity_penalty(self, selected_trends: List[SelectedTrend],
                                  candidate_domains: List[str],
                                  candidate_sources: List[str]) -> float:
        """
        Calculate penalty for lack of diversity.
        
        Returns penalty factor (0.0 to 1.0, where 1.0 = no penalty)
        """
        if not selected_trends:
            return 1.0
        
        # Count existing domains and sources
        existing_domains = set()
        existing_sources = set()
        
        for trend in selected_trends:
            # Get cluster data to extract domains/sources
            # This is simplified - in practice, you'd query the database
            pass  # TODO: Implement based on available data structure
        
        # For now, return no penalty (simplified implementation)
        return 1.0
    
    def calculate_freshness_boost(self, avg_age_hours: float) -> float:
        """
        Calculate boost factor for fresh content.
        
        Returns boost factor (1.0 to 1.5)
        """
        if avg_age_hours <= FRESHNESS_BOOST_HOURS:
            # Linear boost for very fresh content
            boost = 1.0 + (FRESHNESS_BOOST_HOURS - avg_age_hours) / FRESHNESS_BOOST_HOURS * 0.2
            return min(1.2, boost)
        else:
            return 1.0
    
    def select_global_top_k(self, scored_clusters: List[ClusterMetrics],
                          cluster_data: Dict[int, Dict[str, Any]],
                          top_k: int = DEFAULT_TOP_K) -> List[SelectedTrend]:
        """
        Select top-K trending topics globally with diversity considerations.
        
        Args:
            scored_clusters: List of scored clusters
            cluster_data: Dictionary mapping cluster_id to cluster data with items
            top_k: Number of trends to select
            
        Returns:
            List of selected trending topics
        """
        if not scored_clusters:
            return []
        
        # Filter by minimum score
        candidates = [c for c in scored_clusters if c.composite_score >= self.min_score]
        
        if not candidates:
            logger.warning(f"No clusters meet minimum score threshold {self.min_score}")
            return []
        
        logger.info(f"Selecting top {top_k} from {len(candidates)} candidates")
        
        selected_trends = []
        used_domains = defaultdict(int)
        used_sources = defaultdict(int)
        
        for rank, cluster_metrics in enumerate(candidates):
            if len(selected_trends) >= top_k:
                break
            
            cluster_id = cluster_metrics.cluster_id
            cluster_info = cluster_data.get(cluster_id, {})
            
            if not cluster_info.get('items'):
                continue
            
            # Extract cluster information
            title, summary, domains = self.extract_cluster_info(cluster_info)
            
            # Calculate diversity penalty
            diversity_penalty = self.calculate_diversity_penalty(
                selected_trends, domains, []  # Simplified
            )
            
            # Calculate freshness boost
            freshness_boost = self.calculate_freshness_boost(cluster_metrics.avg_age_hours)
            
            # Calculate adjusted score
            adjusted_score = (
                cluster_metrics.composite_score * 
                diversity_penalty * 
                freshness_boost
            )
            
            # Create selected trend
            trend = SelectedTrend(
                cluster_id=cluster_id,
                rank=len(selected_trends) + 1,
                score=cluster_metrics.composite_score,
                adjusted_score=adjusted_score,
                title=title,
                summary=summary,
                item_count=cluster_metrics.item_count,
                unique_sources=cluster_metrics.unique_sources,
                avg_age_hours=cluster_metrics.avg_age_hours,
                representative_items=cluster_info.get('items', [])[:3]  # Top 3 items
            )
            
            selected_trends.append(trend)
            
            # Update domain/source tracking
            for domain in domains:
                used_domains[domain] += 1
        
        # Sort by adjusted score
        selected_trends.sort(key=lambda x: x.adjusted_score, reverse=True)
        
        # Update final ranks
        for i, trend in enumerate(selected_trends):
            trend.rank = i + 1
        
        logger.info(f"Selected {len(selected_trends)} trending topics")
        
        return selected_trends
    
    def select_topic_specific(self, scored_clusters: List[ClusterMetrics],
                            cluster_data: Dict[int, Dict[str, Any]],
                            topic_keywords: List[str],
                            top_k: int = 20) -> List[SelectedTrend]:
        """
        Select top-K trends for a specific topic.
        
        Args:
            scored_clusters: List of scored clusters
            cluster_data: Dictionary mapping cluster_id to cluster data
            topic_keywords: Keywords for topic filtering
            top_k: Number of trends to select for this topic
            
        Returns:
            List of topic-specific trending topics
        """
        if not scored_clusters or not topic_keywords:
            return []
        
        # Filter clusters relevant to topic
        relevant_clusters = []
        
        for cluster_metrics in scored_clusters:
            cluster_id = cluster_metrics.cluster_id
            cluster_info = cluster_data.get(cluster_id, {})
            items = cluster_info.get('items', [])
            
            if not items:
                continue
            
            # Check if cluster is relevant to topic
            relevance_score = self.calculate_topic_relevance(items, topic_keywords)
            
            if relevance_score > 0.1:  # Minimum relevance threshold
                # Boost score by relevance
                boosted_score = cluster_metrics.composite_score * (1 + relevance_score)
                
                # Create modified metrics with boosted score
                relevant_clusters.append((
                    cluster_metrics._replace(composite_score=boosted_score),
                    relevance_score
                ))
        
        if not relevant_clusters:
            logger.info(f"No clusters relevant to topic keywords: {topic_keywords}")
            return []
        
        # Sort by boosted score
        relevant_clusters.sort(key=lambda x: x[0].composite_score, reverse=True)
        
        # Select top-K
        selected_trends = []
        
        for i, (cluster_metrics, relevance) in enumerate(relevant_clusters[:top_k]):
            cluster_id = cluster_metrics.cluster_id
            cluster_info = cluster_data.get(cluster_id, {})
            
            title, summary, domains = self.extract_cluster_info(cluster_info)
            
            trend = SelectedTrend(
                cluster_id=cluster_id,
                rank=i + 1,
                score=cluster_metrics.composite_score,
                adjusted_score=cluster_metrics.composite_score,
                title=title,
                summary=summary,
                item_count=cluster_metrics.item_count,
                unique_sources=cluster_metrics.unique_sources,
                avg_age_hours=cluster_metrics.avg_age_hours,
                topic_category=" ".join(topic_keywords),
                representative_items=cluster_info.get('items', [])[:3]
            )
            
            selected_trends.append(trend)
        
        logger.info(f"Selected {len(selected_trends)} trends for topic: {topic_keywords}")
        
        return selected_trends
    
    def calculate_topic_relevance(self, items: List[Dict[str, Any]], 
                                keywords: List[str]) -> float:
        """
        Calculate how relevant a cluster is to topic keywords.
        
        Returns relevance score (0.0 to 1.0)
        """
        if not items or not keywords:
            return 0.0
        
        # Normalize keywords
        normalized_keywords = [kw.lower().strip() for kw in keywords]
        
        relevance_scores = []
        
        for item in items:
            item_score = 0.0
            item_text = ""
            
            # Combine title and summary for analysis
            if item.get('title'):
                item_text += item['title'].lower() + " "
            if item.get('summary'):
                item_text += item['summary'].lower() + " "
            
            if not item_text.strip():
                continue
            
            # Count keyword matches
            for keyword in normalized_keywords:
                if keyword in item_text:
                    # Boost score for exact matches
                    item_score += 1.0
                    
                    # Additional boost for title matches
                    if item.get('title') and keyword in item['title'].lower():
                        item_score += 0.5
            
            # Normalize by number of keywords
            if normalized_keywords:
                item_score /= len(normalized_keywords)
            
            relevance_scores.append(min(1.0, item_score))
        
        # Return average relevance across all items
        return sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0


async def select_trending_topics(session: AsyncSession,
                                scored_clusters: List[ClusterMetrics],
                                top_k: int = DEFAULT_TOP_K,
                                topic_keywords: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Select trending topics from scored clusters.
    
    Args:
        session: Database session
        scored_clusters: List of scored cluster metrics
        top_k: Number of trends to select
        topic_keywords: Optional topic keywords for focused selection
        
    Returns:
        Dictionary with selected trends and statistics
    """
    start_time = time.time()
    
    try:
        if not scored_clusters:
            return {
                'runtime_seconds': time.time() - start_time,
                'trends_selected': 0,
                'global_trends': [],
                'topic_trends': []
            }
        
        # Get cluster data with items
        from newsbot.core.repositories import get_cluster_with_items
        
        cluster_data = {}
        for cluster_metrics in scored_clusters:
            cluster_info = await get_cluster_with_items(session, cluster_metrics.cluster_id)
            if cluster_info:
                cluster_data[cluster_metrics.cluster_id] = cluster_info
        
        selector = TrendingSelector()
        
        # Global selection
        global_trends = selector.select_global_top_k(
            scored_clusters, cluster_data, top_k
        )
        
        # Topic-specific selection if keywords provided
        topic_trends = []
        if topic_keywords:
            topic_trends = selector.select_topic_specific(
                scored_clusters, cluster_data, topic_keywords, top_k // 2
            )
        
        runtime = time.time() - start_time
        
        logger.info(
            f"Selected {len(global_trends)} global trends, "
            f"{len(topic_trends)} topic trends in {runtime:.2f}s"
        )
        
        return {
            'runtime_seconds': runtime,
            'trends_selected': len(global_trends) + len(topic_trends),
            'global_trends': [t.to_dict() for t in global_trends],
            'topic_trends': [t.to_dict() for t in topic_trends],
            'selection_stats': {
                'total_candidates': len(scored_clusters),
                'global_selected': len(global_trends),
                'topic_selected': len(topic_trends),
                'top_global_score': global_trends[0].adjusted_score if global_trends else 0,
                'avg_global_score': sum(t.adjusted_score for t in global_trends) / len(global_trends) if global_trends else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Trend selection failed: {e}")
        return {
            'runtime_seconds': time.time() - start_time,
            'trends_selected': 0,
            'global_trends': [],
            'topic_trends': [],
            'error': str(e)
        }


async def run_selection_pipeline(window_hours: int = 24,
                               top_k: int = DEFAULT_TOP_K,
                               topic_keywords: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Run complete trend selection pipeline.
    
    Args:
        window_hours: Time window for analysis
        top_k: Number of trends to select
        topic_keywords: Optional topic keywords
        
    Returns:
        Selection results and statistics
    """
    async with AsyncSessionLocal() as session:
        # Get scored clusters
        from newsbot.trender.score import score_all_clusters
        
        scored_clusters = await score_all_clusters(session, window_hours)
        
        if not scored_clusters:
            return {
                'runtime_seconds': 0,
                'trends_selected': 0,
                'global_trends': [],
                'topic_trends': []
            }
        
        # Select trending topics
        return await select_trending_topics(
            session, scored_clusters, top_k, topic_keywords
        )