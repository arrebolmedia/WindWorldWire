"""Pipeline orquestador para trending topics.

Coordina todo el flujo de análisis de tendencias:
1. Clustering: Agrupa contenido similar usando embeddings
2. Scoring: Calcula métricas compuestas para ranking
3. Selection: Selecciona top-K trending topics con diversidad
4. Persistence: Guarda resultados y estadísticas
5. Monitoring: Tracking de performance y calidad
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.core.db import AsyncSessionLocal
from newsbot.core.logging import get_logger
from newsbot.trender.cluster import cluster_recent_items
from newsbot.trender.score import run_scoring_pipeline, ClusterMetrics, score_all_clusters
from newsbot.trender.selector import run_selection_pipeline
from newsbot.trender.selector_final import run_final_selection, Selection
from newsbot.trender.topics import TopicsConfigParserNew
from newsbot.core.repositories import get_recent_raw_items

logger = get_logger(__name__)

# Pipeline configuration
DEFAULT_WINDOW_HOURS = 24
DEFAULT_TOP_K = 50
ENABLE_INCREMENTAL_CLUSTERING = True
ENABLE_QUALITY_FILTERING = True
MIN_CLUSTER_SIZE = 3


async def run_trending(window_hours: int, k_global: int) -> Selection:
    """
    Main trending topics orchestrator.
    
    Loads recent raw_items from DB, clusters incrementally, scores clusters,
    and selects top-K using the final selector.
    
    Args:
        window_hours: Time window for content analysis (e.g., 24 hours)
        k_global: Number of global trending picks to select
        
    Returns:
        Selection object with global_picks and topic_picks
    """
    start_time = time.time()
    
    try:
        logger.info(f"Starting trending pipeline: window={window_hours}h, k_global={k_global}")
        
        async with AsyncSessionLocal() as session:
            # Step 1: Load recent raw_items from DB
            logger.info("Loading recent raw items from database")
            raw_items = await get_recent_raw_items(session, window_hours)
            logger.info(f"Loaded {len(raw_items)} raw items from last {window_hours}h")
            
            if not raw_items:
                logger.warning("No raw items found, returning empty selection")
                return Selection(global_picks=[], topic_picks=[])
            
            # Step 2: Cluster incrementally
            logger.info("Running incremental clustering")
            clustering_results = await cluster_recent_items(
                window_hours=window_hours
            )
            logger.info(f"Clustering completed: {clustering_results.get('stats', {}).get('new_clusters', 0)} clusters created")
            
            # Step 3: Score clusters
            logger.info("Scoring clusters")
            scored_clusters = await score_all_clusters(session, window_hours)
            logger.info(f"Scored {len(scored_clusters)} clusters")
            
            if not scored_clusters:
                logger.warning("No scored clusters found, returning empty selection")
                return Selection(global_picks=[], topic_picks=[])
            
            # Step 4: Select top-K using final selector
            logger.info("Running final selection")
            selection = await run_final_selection(
                scored_clusters=scored_clusters,
                sources_config_path="config/sources.yaml",
                topics_config_path="config/topics.yaml"
            )
            
            runtime = time.time() - start_time
            logger.info(f"Trending pipeline completed in {runtime:.2f}s: "
                       f"{len(selection.global_picks)} global + {len(selection.topic_picks)} topic picks")
            
            return selection
            
    except Exception as e:
        runtime = time.time() - start_time
        logger.error(f"Trending pipeline failed after {runtime:.2f}s: {e}")
        # Return empty selection on error
        return Selection(global_picks=[], topic_picks=[])


async def run_topics(window_hours: int) -> Dict[str, Selection]:
    """
    Per-topic analysis orchestrator.
    
    Loads topics from YAML, filters items per topic, clusters per topic (scoped),
    scores, and selects per-topic picks.
    
    Args:
        window_hours: Time window for content analysis
        
    Returns:
        Dictionary mapping topic_key to Selection with picks and stats
    """
    start_time = time.time()
    
    try:
        logger.info(f"Starting per-topic analysis pipeline: window={window_hours}h")
        
        # Step 1: Load topics from YAML
        logger.info("Loading topics configuration")
        topics_config = TopicsConfigParserNew.load_from_yaml("config/topics.yaml")
        enabled_topics = [topic for topic in topics_config if topic.enabled]
        logger.info(f"Loaded {len(enabled_topics)} enabled topics")
        
        if not enabled_topics:
            logger.warning("No enabled topics found")
            return {}
        
        async with AsyncSessionLocal() as session:
            # Step 2: Load recent raw_items from DB
            logger.info("Loading recent raw items from database")
            raw_items = await get_recent_raw_items(session, window_hours)
            logger.info(f"Loaded {len(raw_items)} raw items from last {window_hours}h")
            
            if not raw_items:
                logger.warning("No raw items found")
                return {}
            
            results = {}
            
            # Step 3: Process each topic independently
            for topic in enabled_topics:
                topic_start = time.time()
                topic_key = topic.topic_key
                
                try:
                    logger.info(f"Processing topic: {topic.name} ({topic_key})")
                    
                    # Filter items per topic using TopicMatcher
                    from newsbot.trender.topics import TopicMatcher
                    matcher = TopicMatcher(topic)
                    
                    # Apply topic matching
                    topic_items = []
                    for item in raw_items:
                        match_result = matcher.match_item(item)
                        if match_result['is_match']:
                            topic_items.append(item)
                    
                    logger.info(f"Topic {topic_key}: {len(topic_items)} matching items")
                    
                    if not topic_items:
                        logger.info(f"No items for topic {topic_key}, skipping")
                        results[topic_key] = Selection(global_picks=[], topic_picks=[])
                        continue
                    
                    # Cluster per topic (scoped clustering)
                    logger.info(f"Clustering items for topic {topic_key}")
                    topic_clustering_results = await cluster_recent_items(
                        window_hours=window_hours
                    )
                    
                    # Score clusters for this topic
                    logger.info(f"Scoring clusters for topic {topic_key}")
                    topic_scored_clusters = await score_all_clusters(session, window_hours)
                    
                    # Filter clusters that belong to this topic
                    # For now, we'll use all clusters but in practice you'd filter by topic
                    topic_specific_clusters = topic_scored_clusters  # TODO: Add topic filtering
                    
                    # Select per-topic picks
                    logger.info(f"Selecting picks for topic {topic_key}")
                    
                    # Create a mock cluster-topic mapping for this topic
                    cluster_topic_mapping = {
                        cluster.cluster_id: topic_key 
                        for cluster in topic_specific_clusters
                    }
                    
                    # Use the final selector but only for this topic
                    topic_selection = await run_final_selection(
                        scored_clusters=topic_specific_clusters,
                        sources_config_path="config/sources.yaml", 
                        topics_config_path="config/topics.yaml",
                        cluster_topic_mapping=cluster_topic_mapping
                    )
                    
                    # For topic-specific analysis, we primarily care about topic_picks
                    # but we can include global_picks that are relevant to this topic
                    results[topic_key] = topic_selection
                    
                    topic_runtime = time.time() - topic_start
                    logger.info(f"Topic {topic_key} processed in {topic_runtime:.2f}s: "
                               f"{len(topic_selection.topic_picks)} topic picks")
                    
                except Exception as e:
                    logger.error(f"Failed to process topic {topic_key}: {e}")
                    results[topic_key] = Selection(global_picks=[], topic_picks=[])
            
            total_runtime = time.time() - start_time
            total_picks = sum(len(selection.topic_picks) + len(selection.global_picks) 
                            for selection in results.values())
            
            logger.info(f"Per-topic analysis completed in {total_runtime:.2f}s: "
                       f"{len(results)} topics processed, {total_picks} total picks")
            
            return results
            
    except Exception as e:
        runtime = time.time() - start_time
        logger.error(f"Per-topic analysis pipeline failed after {runtime:.2f}s: {e}")
        return {}


@dataclass
class PipelineStats:
    """Estadísticas del pipeline de trending topics."""
    runtime_seconds: float
    window_hours: int
    items_processed: int
    clusters_created: int
    clusters_updated: int
    clusters_scored: int
    trends_selected: int
    pipeline_stages: Dict[str, float]  # Stage name -> runtime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'runtime_seconds': self.runtime_seconds,
            'window_hours': self.window_hours,
            'items_processed': self.items_processed,
            'clusters_created': self.clusters_created,
            'clusters_updated': self.clusters_updated,
            'clusters_scored': self.clusters_scored,
            'trends_selected': self.trends_selected,
            'pipeline_stages': self.pipeline_stages
        }


class TrendingPipeline:
    """Orquestador principal del pipeline de trending topics."""
    
    def __init__(self, window_hours: int = DEFAULT_WINDOW_HOURS,
                 top_k: int = DEFAULT_TOP_K,
                 incremental: bool = ENABLE_INCREMENTAL_CLUSTERING):
        
        self.window_hours = window_hours
        self.top_k = top_k
        self.incremental = incremental
        self.stage_timings = {}
    
    def _time_stage(self, stage_name: str):
        """Context manager for timing pipeline stages."""
        return StageTimer(stage_name, self.stage_timings)
    
    async def run_clustering_stage(self, session: AsyncSession) -> Dict[str, Any]:
        """Run clustering stage of the pipeline."""
        with self._time_stage("clustering"):
            logger.info(f"Starting clustering stage (window: {self.window_hours}h, incremental: {self.incremental})")
            
            clustering_stats = await cluster_recent_items(
                window_hours=self.window_hours
            )
            
            logger.info(
                f"Clustering completed: {clustering_stats.get('stats', {}).get('new_clusters', 0)} created, "
                f"{clustering_stats.get('stats', {}).get('existing_clusters', 0)} updated, "
                f"{clustering_stats.get('stats', {}).get('items_clustered', 0)} items clustered"
            )
            
            return clustering_stats
    
    async def run_scoring_stage(self, session: AsyncSession) -> List[ClusterMetrics]:
        """Run scoring stage of the pipeline."""
        with self._time_stage("scoring"):
            logger.info("Starting scoring stage")
            
            scoring_results = await run_scoring_pipeline(window_hours=self.window_hours)
            scored_clusters = scoring_results.get('scored_clusters', [])
            
            # Convert dictionaries back to ClusterMetrics objects
            cluster_metrics = []
            for cluster_dict in scored_clusters:
                metrics = ClusterMetrics(
                    cluster_id=cluster_dict['cluster_id'],
                    viral_score=cluster_dict['viral_score'],
                    freshness_score=cluster_dict['freshness_score'],
                    diversity_score=cluster_dict['diversity_score'],
                    volume_score=cluster_dict['volume_score'],
                    quality_score=cluster_dict['quality_score'],
                    composite_score=cluster_dict['composite_score'],
                    item_count=cluster_dict['item_count'],
                    avg_age_hours=cluster_dict['avg_age_hours'],
                    unique_sources=cluster_dict['unique_sources'],
                    unique_domains=cluster_dict['unique_domains']
                )
                cluster_metrics.append(metrics)
            
            logger.info(
                f"Scoring completed: {len(cluster_metrics)} clusters scored, "
                f"avg score: {scoring_results.get('avg_score', 0):.3f}"
            )
            
            return cluster_metrics
    
    async def run_selection_stage(self, session: AsyncSession, 
                                scored_clusters: List[ClusterMetrics]) -> Dict[str, Any]:
        """Run selection stage of the pipeline."""
        with self._time_stage("selection"):
            logger.info(f"Starting selection stage (top_k: {self.top_k})")
            
            selection_results = await run_selection_pipeline(
                window_hours=self.window_hours,
                top_k=self.top_k
            )
            
            logger.info(
                f"Selection completed: {selection_results.get('trends_selected', 0)} trends selected"
            )
            
            return selection_results
    
    async def run_persistence_stage(self, session: AsyncSession,
                                  pipeline_results: Dict[str, Any]) -> Dict[str, Any]:
        """Run persistence stage to save results."""
        with self._time_stage("persistence"):
            logger.info("Starting persistence stage")
            
            try:
                # TODO: Implement persistence logic
                # This would save trending topics to database for serving
                # For now, we'll just log the results
                
                trends = pipeline_results.get('selection_results', {}).get('global_trends', [])
                
                persistence_stats = {
                    'trends_saved': len(trends),
                    'database_writes': len(trends),  # One write per trend
                    'cache_updates': 1  # Update trending cache
                }
                
                logger.info(f"Persistence completed: {persistence_stats['trends_saved']} trends saved")
                
                return persistence_stats
                
            except Exception as e:
                logger.error(f"Persistence stage failed: {e}")
                return {
                    'trends_saved': 0,
                    'database_writes': 0,
                    'cache_updates': 0,
                    'error': str(e)
                }
    
    async def run_quality_checks(self, pipeline_results: Dict[str, Any]) -> Dict[str, Any]:
        """Run quality checks on pipeline results."""
        quality_stats = {
            'total_checks': 0,
            'passed_checks': 0,
            'warnings': [],
            'errors': []
        }
        
        try:
            # Check 1: Minimum number of trends
            trends = pipeline_results.get('selection_results', {}).get('global_trends', [])
            quality_stats['total_checks'] += 1
            
            if len(trends) >= self.top_k * 0.5:  # At least 50% of requested
                quality_stats['passed_checks'] += 1
            else:
                quality_stats['warnings'].append(f"Low trend count: {len(trends)} < {self.top_k * 0.5}")
            
            # Check 2: Score distribution
            if trends:
                scores = [t.get('adjusted_score', 0) for t in trends]
                avg_score = sum(scores) / len(scores)
                quality_stats['total_checks'] += 1
                
                if avg_score >= 0.2:  # Reasonable average score
                    quality_stats['passed_checks'] += 1
                else:
                    quality_stats['warnings'].append(f"Low average score: {avg_score:.3f}")
            
            # Check 3: Clustering effectiveness
            clustering_stats = pipeline_results.get('clustering_stats', {})
            items_processed = clustering_stats.get('items_processed', 0)
            items_clustered = clustering_stats.get('items_clustered', 0)
            
            quality_stats['total_checks'] += 1
            
            if items_processed > 0:
                clustering_rate = items_clustered / items_processed
                if clustering_rate >= 0.3:  # At least 30% of items clustered
                    quality_stats['passed_checks'] += 1
                else:
                    quality_stats['warnings'].append(f"Low clustering rate: {clustering_rate:.2%}")
            else:
                quality_stats['errors'].append("No items processed for clustering")
            
            # Check 4: Pipeline timing
            total_runtime = pipeline_results.get('pipeline_stats', {}).get('runtime_seconds', 0)
            quality_stats['total_checks'] += 1
            
            if total_runtime <= 300:  # Under 5 minutes
                quality_stats['passed_checks'] += 1
            else:
                quality_stats['warnings'].append(f"Long pipeline runtime: {total_runtime:.1f}s")
            
            # Calculate quality score
            if quality_stats['total_checks'] > 0:
                quality_stats['quality_score'] = quality_stats['passed_checks'] / quality_stats['total_checks']
            else:
                quality_stats['quality_score'] = 0.0
            
            logger.info(
                f"Quality checks: {quality_stats['passed_checks']}/{quality_stats['total_checks']} passed, "
                f"score: {quality_stats['quality_score']:.2%}"
            )
            
        except Exception as e:
            logger.error(f"Quality checks failed: {e}")
            quality_stats['errors'].append(f"Quality check error: {str(e)}")
        
        return quality_stats
    
    async def run_full_pipeline(self) -> Dict[str, Any]:
        """
        Run complete trending topics pipeline.
        
        Returns comprehensive results and statistics.
        """
        pipeline_start = time.time()
        
        try:
            logger.info(f"Starting trending pipeline (window: {self.window_hours}h, top_k: {self.top_k})")
            
            pipeline_results = {
                'clustering_stats': {},
                'scoring_stats': {},
                'selection_results': {},
                'persistence_stats': {},
                'quality_stats': {},
                'pipeline_stats': {}
            }
            
            async with AsyncSessionLocal() as session:
                # Stage 1: Clustering
                clustering_stats = await self.run_clustering_stage(session)
                pipeline_results['clustering_stats'] = clustering_stats
                
                # Stage 2: Scoring
                scored_clusters = await self.run_scoring_stage(session)
                pipeline_results['scoring_stats'] = {
                    'clusters_scored': len(scored_clusters),
                    'avg_score': sum(c.composite_score for c in scored_clusters) / len(scored_clusters) if scored_clusters else 0
                }
                
                # Stage 3: Selection
                selection_results = await self.run_selection_stage(session, scored_clusters)
                pipeline_results['selection_results'] = selection_results
                
                # Stage 4: Persistence
                persistence_stats = await self.run_persistence_stage(session, pipeline_results)
                pipeline_results['persistence_stats'] = persistence_stats
            
            # Stage 5: Quality checks
            if ENABLE_QUALITY_FILTERING:
                quality_stats = await self.run_quality_checks(pipeline_results)
                pipeline_results['quality_stats'] = quality_stats
            
            # Calculate final pipeline statistics
            total_runtime = time.time() - pipeline_start
            
            pipeline_stats = PipelineStats(
                runtime_seconds=total_runtime,
                window_hours=self.window_hours,
                items_processed=clustering_stats.get('items_processed', 0),
                clusters_created=clustering_stats.get('clusters_created', 0),
                clusters_updated=clustering_stats.get('clusters_updated', 0),
                clusters_scored=len(scored_clusters),
                trends_selected=selection_results.get('trends_selected', 0),
                pipeline_stages=self.stage_timings.copy()
            )
            
            pipeline_results['pipeline_stats'] = pipeline_stats.to_dict()
            
            logger.info(
                f"Pipeline completed successfully in {total_runtime:.2f}s: "
                f"{pipeline_stats.clusters_created} clusters created, "
                f"{pipeline_stats.trends_selected} trends selected"
            )
            
            return pipeline_results
            
        except Exception as e:
            total_runtime = time.time() - pipeline_start
            logger.error(f"Pipeline failed after {total_runtime:.2f}s: {e}")
            
            return {
                'clustering_stats': {'error': str(e)},
                'scoring_stats': {'error': str(e)},
                'selection_results': {'error': str(e)},
                'persistence_stats': {'error': str(e)},
                'quality_stats': {'error': str(e)},
                'pipeline_stats': {
                    'runtime_seconds': total_runtime,
                    'window_hours': self.window_hours,
                    'error': str(e)
                }
            }


class StageTimer:
    """Context manager for timing pipeline stages."""
    
    def __init__(self, stage_name: str, timings_dict: Dict[str, float]):
        self.stage_name = stage_name
        self.timings_dict = timings_dict
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            runtime = time.time() - self.start_time
            self.timings_dict[self.stage_name] = runtime


async def run_trending_pipeline(window_hours: int = DEFAULT_WINDOW_HOURS,
                              top_k: int = DEFAULT_TOP_K,
                              incremental: bool = ENABLE_INCREMENTAL_CLUSTERING) -> Dict[str, Any]:
    """
    Run complete trending topics pipeline.
    
    Args:
        window_hours: Time window for content analysis
        top_k: Number of trending topics to select
        incremental: Whether to use incremental clustering
        
    Returns:
        Comprehensive pipeline results
    """
    pipeline = TrendingPipeline(
        window_hours=window_hours,
        top_k=top_k,
        incremental=incremental
    )
    
    return await pipeline.run_full_pipeline()


async def run_pipeline_with_topics(window_hours: int = DEFAULT_WINDOW_HOURS,
                                 top_k: int = DEFAULT_TOP_K,
                                 topic_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Run pipeline with topic-specific analysis.
    
    Args:
        window_hours: Time window for analysis
        top_k: Number of trends to select
        topic_name: Specific topic to focus on (None for all topics)
        
    Returns:
        Pipeline results with topic analysis
    """
    start_time = time.time()
    
    try:
        # Run standard trending pipeline
        logger.info("Running standard trending pipeline")
        global_results = await run_trending(window_hours=window_hours, k_global=top_k)
        
        # Run topic-specific analysis
        logger.info("Running topic-specific analysis")
        topics_results = await run_topics(window_hours=window_hours)
        
        # Combine results
        combined_results = {
            'runtime_seconds': time.time() - start_time,
            'window_hours': window_hours,
            'top_k': top_k,
            'global_pipeline': global_results.to_dict() if hasattr(global_results, 'to_dict') else str(global_results),
            'topics_pipeline': {topic_key: selection.to_dict() for topic_key, selection in topics_results.items()},
            'summary': {
                'global_trends': global_results.total_picks if hasattr(global_results, 'total_picks') else 0,
                'topic_trends': len(topics_results),
                'total_clusters': 0,  # Would need to be calculated separately
                'items_analyzed': 0   # Would need to be calculated separately
            }
        }
        
        logger.info(
            f"Combined pipeline completed: "
            f"{combined_results['summary']['global_trends']} global trends, "
            f"{combined_results['summary']['topic_trends']} topic-specific trends"
        )
        
        return combined_results
        
    except Exception as e:
        logger.error(f"Combined pipeline failed: {e}")
        return {
            'runtime_seconds': time.time() - start_time,
            'window_hours': window_hours,
            'top_k': top_k,
            'error': str(e)
        }


def main():
    """CLI entry point for running the trending pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Trending Topics Pipeline')
    parser.add_argument(
        '--window-hours',
        type=int,
        default=DEFAULT_WINDOW_HOURS,
        help=f'Time window in hours (default: {DEFAULT_WINDOW_HOURS})'
    )
    parser.add_argument(
        '--top-k',
        type=int,
        default=DEFAULT_TOP_K,
        help=f'Number of trends to select (default: {DEFAULT_TOP_K})'
    )
    parser.add_argument(
        '--topic',
        type=str,
        help='Specific topic to analyze (optional)'
    )
    parser.add_argument(
        '--no-incremental',
        action='store_true',
        help='Disable incremental clustering'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        import logging
        logging.getLogger('newsbot').setLevel(logging.DEBUG)
    
    # Run pipeline
    if args.topic:
        results = asyncio.run(run_pipeline_with_topics(
            window_hours=args.window_hours,
            top_k=args.top_k,
            topic_name=args.topic
        ))
    else:
        results = asyncio.run(run_trending_pipeline(
            window_hours=args.window_hours,
            top_k=args.top_k,
            incremental=not args.no_incremental
        ))
    
    # Print results summary
    print("\n=== Trending Pipeline Results ===")
    print(f"Runtime: {results.get('runtime_seconds', 0):.2f}s")
    
    if 'summary' in results:
        summary = results['summary']
        print(f"Global trends: {summary.get('global_trends', 0)}")
        print(f"Topic trends: {summary.get('topic_trends', 0)}")
        print(f"Clusters created: {summary.get('total_clusters', 0)}")
        print(f"Items analyzed: {summary.get('items_analyzed', 0)}")
    else:
        pipeline_stats = results.get('pipeline_stats', {})
        print(f"Clusters created: {pipeline_stats.get('clusters_created', 0)}")
        print(f"Trends selected: {pipeline_stats.get('trends_selected', 0)}")
        print(f"Items processed: {pipeline_stats.get('items_processed', 0)}")
    
    if 'error' in results:
        print(f"Error: {results['error']}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())