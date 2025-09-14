"""Selector de picks finales para trending topics.

Implementa políticas de selección específicas:
- Selección global: top K_global clusters por score_total con límite de max_posts_per_run
- Selección por tema: hasta topic.max_posts_per_run por tema, ordenados por topic.priority * score_total
- Evita duplicados: si clusters se superponen (similaridad de centroide ≥ 0.9), mantiene el de mayor prioridad
- Retorna Selection con global_picks y topic_picks
"""

import asyncio
import time
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple, Union
from dataclasses import dataclass
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.core.db import AsyncSessionLocal
from newsbot.core.logging import get_logger
from newsbot.trender.score import ClusterMetrics
from newsbot.trender.topics import TopicsConfigParserNew, TopicConfig

logger = get_logger(__name__)

# Default thresholds
DEFAULT_SIMILARITY_THRESHOLD = 0.9
DEFAULT_K_GLOBAL = 50


@dataclass
class SelectedPick:
    """Un pick seleccionado final."""
    cluster_id: int
    score_total: float
    adjusted_score: float
    selection_type: str  # 'global' or 'topic'
    topic_key: Optional[str] = None
    topic_priority: Optional[float] = None
    rank: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'cluster_id': self.cluster_id,
            'score_total': self.score_total,
            'adjusted_score': self.adjusted_score,
            'selection_type': self.selection_type,
            'topic_key': self.topic_key,
            'topic_priority': self.topic_priority,
            'rank': self.rank
        }


@dataclass
class Selection:
    """Resultado final de selección con picks globales y por tema."""
    global_picks: List[SelectedPick]
    topic_picks: List[SelectedPick]
    
    @property
    def total_picks(self) -> int:
        """Total number of picks selected."""
        return len(self.global_picks) + len(self.topic_picks)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'global_picks': [pick.to_dict() for pick in self.global_picks],
            'topic_picks': [pick.to_dict() for pick in self.topic_picks],
            'total_picks': self.total_picks,
            'stats': {
                'global_count': len(self.global_picks),
                'topic_count': len(self.topic_picks),
                'topics_represented': len(set(pick.topic_key for pick in self.topic_picks if pick.topic_key))
            }
        }


class PickSelector:
    """Selector final de picks con políticas específicas."""
    
    def __init__(self, similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD):
        self.similarity_threshold = similarity_threshold
    
    def calculate_centroid_similarity(self, cluster1_id: int, cluster2_id: int,
                                    cluster_centroids: Dict[int, np.ndarray]) -> float:
        """
        Calculate cosine similarity between cluster centroids.
        
        Args:
            cluster1_id: First cluster ID
            cluster2_id: Second cluster ID
            cluster_centroids: Dictionary mapping cluster_id to centroid vector
            
        Returns:
            Cosine similarity (0.0 to 1.0)
        """
        if cluster1_id not in cluster_centroids or cluster2_id not in cluster_centroids:
            return 0.0
        
        centroid1 = cluster_centroids[cluster1_id]
        centroid2 = cluster_centroids[cluster2_id]
        
        # Calculate cosine similarity
        dot_product = np.dot(centroid1, centroid2)
        norm1 = np.linalg.norm(centroid1)
        norm2 = np.linalg.norm(centroid2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        return max(0.0, min(1.0, similarity))  # Clamp to [0, 1]
    
    def select_global_picks(self, scored_clusters: List[ClusterMetrics],
                          sources_config: Dict[str, Any],
                          cluster_centroids: Optional[Dict[int, np.ndarray]] = None) -> List[SelectedPick]:
        """
        Select global trending picks.
        
        Args:
            scored_clusters: List of scored clusters
            sources_config: Configuration from sources.yaml
            cluster_centroids: Optional centroids for similarity calculation
            
        Returns:
            List of selected global picks
        """
        if not scored_clusters:
            return []
        
        # Get K_global and max_posts_per_run from sources config
        k_global = sources_config.get('k_global', DEFAULT_K_GLOBAL)
        max_posts_per_run = sources_config.get('max_posts_per_run', 100)
        
        # Apply cap: min(k_global, max_posts_per_run)
        max_picks = min(k_global, max_posts_per_run)
        
        logger.info(f"Selecting global picks: k_global={k_global}, max_posts={max_posts_per_run}, final_limit={max_picks}")
        
        # Sort by composite_score (equivalent to score_total)
        sorted_clusters = sorted(scored_clusters, key=lambda x: x.composite_score, reverse=True)
        
        global_picks = []
        for i, cluster_metrics in enumerate(sorted_clusters[:max_picks]):
            pick = SelectedPick(
                cluster_id=cluster_metrics.cluster_id,
                score_total=cluster_metrics.composite_score,
                adjusted_score=cluster_metrics.composite_score,
                selection_type='global',
                rank=i + 1
            )
            global_picks.append(pick)
        
        logger.info(f"Selected {len(global_picks)} global picks")
        return global_picks
    
    def select_topic_picks(self, scored_clusters: List[ClusterMetrics],
                         topics_config: List[TopicConfig],
                         cluster_topic_mapping: Dict[int, str]) -> List[SelectedPick]:
        """
        Select per-topic picks.
        
        Args:
            scored_clusters: List of scored clusters
            topics_config: List of topic configurations
            cluster_topic_mapping: Maps cluster_id to topic_key
            
        Returns:
            List of selected topic picks
        """
        if not scored_clusters or not topics_config:
            return []
        
        # Create topic lookup
        topics_by_key = {topic.topic_key: topic for topic in topics_config if topic.enabled}
        
        if not topics_by_key:
            logger.info("No enabled topics found")
            return []
        
        # Group clusters by topic
        clusters_by_topic = defaultdict(list)
        for cluster_metrics in scored_clusters:
            topic_key = cluster_topic_mapping.get(cluster_metrics.cluster_id)
            if topic_key and topic_key in topics_by_key:
                clusters_by_topic[topic_key].append(cluster_metrics)
        
        logger.info(f"Found clusters for {len(clusters_by_topic)} topics")
        
        topic_picks = []
        
        for topic_key, topic_clusters in clusters_by_topic.items():
            topic_config = topics_by_key[topic_key]
            
            # Get max posts for this topic
            max_posts = getattr(topic_config, 'max_posts_per_run', 5)
            
            # Calculate adjusted scores: topic.priority * score_total
            priority = getattr(topic_config, 'priority', 1.0)
            
            # Sort by adjusted score
            adjusted_clusters = []
            for cluster_metrics in topic_clusters:
                adjusted_score = priority * cluster_metrics.composite_score
                adjusted_clusters.append((cluster_metrics, adjusted_score))
            
            adjusted_clusters.sort(key=lambda x: x[1], reverse=True)
            
            # Select up to max_posts for this topic
            for i, (cluster_metrics, adjusted_score) in enumerate(adjusted_clusters[:max_posts]):
                pick = SelectedPick(
                    cluster_id=cluster_metrics.cluster_id,
                    score_total=cluster_metrics.composite_score,
                    adjusted_score=adjusted_score,
                    selection_type='topic',
                    topic_key=topic_key,
                    topic_priority=priority,
                    rank=i + 1
                )
                topic_picks.append(pick)
        
        logger.info(f"Selected {len(topic_picks)} topic picks across {len(clusters_by_topic)} topics")
        return topic_picks
    
    def remove_duplicates(self, global_picks: List[SelectedPick],
                        topic_picks: List[SelectedPick],
                        cluster_centroids: Optional[Dict[int, np.ndarray]] = None) -> Tuple[List[SelectedPick], List[SelectedPick]]:
        """
        Remove duplicate picks based on centroid similarity.
        
        When clusters overlap (similarity ≥ threshold), keep the higher-priority path:
        - Topic picks with higher topic.priority win over global picks
        - Among topic picks, higher priority wins
        - Among global picks, higher score wins
        
        Args:
            global_picks: List of global picks
            topic_picks: List of topic picks  
            cluster_centroids: Optional centroids for similarity calculation
            
        Returns:
            Tuple of (filtered_global_picks, filtered_topic_picks)
        """
        if not cluster_centroids:
            logger.warning("No cluster centroids provided, skipping duplicate removal")
            return global_picks, topic_picks
        
        # Find all duplicates
        all_picks = global_picks + topic_picks
        duplicates = set()
        
        for i, pick1 in enumerate(all_picks):
            for j, pick2 in enumerate(all_picks[i+1:], i+1):
                similarity = self.calculate_centroid_similarity(
                    pick1.cluster_id, pick2.cluster_id, cluster_centroids
                )
                
                if similarity >= self.similarity_threshold:
                    # Determine which pick to keep
                    keep_first = self._should_keep_first_pick(pick1, pick2)
                    discard_idx = j if keep_first else i
                    duplicates.add(discard_idx)
                    
                    logger.debug(f"Duplicate found: cluster {pick1.cluster_id} vs {pick2.cluster_id} "
                               f"(similarity: {similarity:.3f}), keeping {'first' if keep_first else 'second'}")
        
        # Filter out duplicates
        filtered_all = [pick for i, pick in enumerate(all_picks) if i not in duplicates]
        
        # Separate back into global and topic picks
        filtered_global = [pick for pick in filtered_all if pick.selection_type == 'global']
        filtered_topic = [pick for pick in filtered_all if pick.selection_type == 'topic']
        
        removed_count = len(duplicates)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} duplicate picks based on centroid similarity")
        
        return filtered_global, filtered_topic
    
    def _should_keep_first_pick(self, pick1: SelectedPick, pick2: SelectedPick) -> bool:
        """
        Determine which pick to keep when there's a duplicate.
        
        Priority order:
        1. Topic picks with higher topic.priority beat everything
        2. Among topic picks, higher priority wins
        3. Global picks beat topic picks with lower priority
        4. Among same type, higher adjusted_score wins
        
        Returns:
            True if should keep pick1, False if should keep pick2
        """
        # Both are topic picks
        if pick1.selection_type == 'topic' and pick2.selection_type == 'topic':
            # Compare topic priorities
            priority1 = pick1.topic_priority or 1.0
            priority2 = pick2.topic_priority or 1.0
            
            if priority1 != priority2:
                return priority1 > priority2
            else:
                # Same priority, use adjusted score
                return pick1.adjusted_score > pick2.adjusted_score
        
        # One topic, one global
        elif pick1.selection_type == 'topic' and pick2.selection_type == 'global':
            # Topic pick wins if its priority is high enough
            # For simplicity, topic picks generally win over global
            return True
        
        elif pick1.selection_type == 'global' and pick2.selection_type == 'topic':
            # Global pick loses to topic pick
            return False
        
        else:  # Both global
            # Higher score wins
            return pick1.adjusted_score > pick2.adjusted_score
    
    def select_final_picks(self, scored_clusters: List[ClusterMetrics],
                         sources_config: Dict[str, Any],
                         topics_config: List[TopicConfig],
                         cluster_topic_mapping: Dict[int, str],
                         cluster_centroids: Optional[Dict[int, np.ndarray]] = None) -> Selection:
        """
        Execute complete selection process.
        
        Args:
            scored_clusters: List of scored clusters
            sources_config: Configuration from sources.yaml
            topics_config: List of topic configurations
            cluster_topic_mapping: Maps cluster_id to topic_key
            cluster_centroids: Optional centroids for similarity calculation
            
        Returns:
            Selection with global and topic picks
        """
        start_time = time.time()
        
        logger.info(f"Starting final pick selection for {len(scored_clusters)} clusters")
        
        # Step 1: Select global picks
        global_picks = self.select_global_picks(scored_clusters, sources_config, cluster_centroids)
        logger.debug(f"Initial global picks: {len(global_picks)}")
        
        # Step 2: Select topic picks
        topic_picks = self.select_topic_picks(scored_clusters, topics_config, cluster_topic_mapping)
        logger.debug(f"Initial topic picks: {len(topic_picks)}")
        
        # Step 3: Remove duplicates
        filtered_global, filtered_topic = self.remove_duplicates(
            global_picks, topic_picks, cluster_centroids
        )
        logger.debug(f"After duplicate removal: {len(filtered_global)} global, {len(filtered_topic)} topic")
        
        # Create final selection
        selection = Selection(
            global_picks=filtered_global,
            topic_picks=filtered_topic
        )
        
        runtime = time.time() - start_time
        logger.info(f"Final selection completed in {runtime:.2f}s: "
                   f"{len(filtered_global)} global + {len(filtered_topic)} topic = {selection.total_picks} total picks")
        
        return selection


async def run_final_selection(scored_clusters: List[ClusterMetrics],
                            sources_config_path: str = "config/sources.yaml",
                            topics_config_path: str = "config/topics.yaml",
                            cluster_topic_mapping: Optional[Dict[int, str]] = None,
                            cluster_centroids: Optional[Dict[int, np.ndarray]] = None) -> Selection:
    """
    Run the final pick selection process.
    
    Args:
        scored_clusters: List of scored clusters
        sources_config_path: Path to sources configuration file
        topics_config_path: Path to topics configuration file
        cluster_topic_mapping: Optional mapping of cluster_id to topic_key
        cluster_centroids: Optional cluster centroids for similarity calculation
        
    Returns:
        Final selection with global and topic picks
    """
    try:
        # Load sources configuration
        import yaml
        with open(sources_config_path, 'r', encoding='utf-8') as f:
            sources_config = yaml.safe_load(f)
        
        # Load topics configuration
        topics_config = TopicsConfigParserNew.load_from_yaml(topics_config_path)
        
        # Use empty mapping if not provided
        if cluster_topic_mapping is None:
            cluster_topic_mapping = {}
        
        # Create selector and run selection
        selector = PickSelector()
        selection = selector.select_final_picks(
            scored_clusters=scored_clusters,
            sources_config=sources_config,
            topics_config=topics_config,
            cluster_topic_mapping=cluster_topic_mapping,
            cluster_centroids=cluster_centroids
        )
        
        return selection
        
    except Exception as e:
        logger.error(f"Final selection failed: {e}")
        # Return empty selection on error
        return Selection(global_picks=[], topic_picks=[])


# Example usage for testing
async def demo_final_selection():
    """Demo function to test the final selection."""
    from newsbot.trender.score import ClusterMetrics
    
    # Mock data for demonstration
    mock_clusters = [
        ClusterMetrics(
            cluster_id=1, viral_score=0.8, freshness_score=0.9, 
            diversity_score=0.7, volume_score=0.6, quality_score=0.8,
            composite_score=0.85, item_count=5, avg_age_hours=2.0,
            unique_sources=3, unique_domains=2
        ),
        ClusterMetrics(
            cluster_id=2, viral_score=0.7, freshness_score=0.8, 
            diversity_score=0.6, volume_score=0.7, quality_score=0.9,
            composite_score=0.75, item_count=8, avg_age_hours=4.0,
            unique_sources=4, unique_domains=3
        ),
        ClusterMetrics(
            cluster_id=3, viral_score=0.9, freshness_score=0.7, 
            diversity_score=0.8, volume_score=0.8, quality_score=0.7,
            composite_score=0.95, item_count=3, avg_age_hours=1.0,
            unique_sources=2, unique_domains=2
        )
    ]
    
    # Mock cluster-topic mapping
    cluster_topic_mapping = {
        1: 'taiwan_seguridad',
        2: 'empresas-negocios', 
        3: 'taiwan_seguridad'
    }
    
    # Mock centroids for similarity testing
    cluster_centroids = {
        1: np.array([0.1, 0.2, 0.3, 0.4]),
        2: np.array([0.9, 0.8, 0.7, 0.6]),
        3: np.array([0.15, 0.25, 0.35, 0.45])  # Similar to cluster 1
    }
    
    # Mock sources config
    mock_sources_config = {
        'k_global': 50,
        'max_posts_per_run': 100
    }
    
    # Create simple topic configs for testing
    mock_topics = [
        TopicConfig(
            name="Taiwán y seguridad regional",
            topic_key="taiwan_seguridad", 
            queries=['"Taiwan"'],
            priority=0.9,
            max_posts_per_run=3,
            enabled=True
        ),
        TopicConfig(
            name="Empresas y Negocios",
            topic_key="empresas-negocios",
            queries=['"business"'],
            priority=0.5,
            max_posts_per_run=2,
            enabled=True
        )
    ]
    
    # Create selector and run selection
    selector = PickSelector()
    selection = selector.select_final_picks(
        scored_clusters=mock_clusters,
        sources_config=mock_sources_config,
        topics_config=mock_topics,
        cluster_topic_mapping=cluster_topic_mapping,
        cluster_centroids=cluster_centroids
    )
    
    print("=== Final Selection Results ===")
    print(f"Global picks: {len(selection.global_picks)}")
    for pick in selection.global_picks:
        print(f"  Cluster {pick.cluster_id}: score={pick.score_total:.3f}, rank={pick.rank}")
    
    print(f"Topic picks: {len(selection.topic_picks)}")
    for pick in selection.topic_picks:
        print(f"  Cluster {pick.cluster_id}: topic={pick.topic_key}, "
              f"priority={pick.topic_priority:.2f}, adjusted_score={pick.adjusted_score:.3f}")
    
    print(f"Total picks: {selection.total_picks}")
    
    return selection


if __name__ == "__main__":
    asyncio.run(demo_final_selection())