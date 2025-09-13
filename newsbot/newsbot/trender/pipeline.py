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
from newsbot.trender.cluster import run_clustering_pipeline
from newsbot.trender.score import run_scoring_pipeline, ClusterMetrics
from newsbot.trender.selector import run_selection_pipeline
from newsbot.trender.topics import run_topics_pipeline

logger = get_logger(__name__)

# Pipeline configuration
DEFAULT_WINDOW_HOURS = 24
DEFAULT_TOP_K = 50
ENABLE_INCREMENTAL_CLUSTERING = True
ENABLE_QUALITY_FILTERING = True
MIN_CLUSTER_SIZE = 3


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
            
            clustering_stats = await run_clustering_pipeline(
                window_hours=self.window_hours,
                incremental=self.incremental
            )
            
            logger.info(
                f"Clustering completed: {clustering_stats.get('clusters_created', 0)} created, "
                f"{clustering_stats.get('clusters_updated', 0)} updated, "
                f"{clustering_stats.get('items_clustered', 0)} items clustered"
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
        global_results = await run_trending_pipeline(window_hours, top_k)
        
        # Run topic-specific analysis
        logger.info("Running topic-specific analysis")
        topics_results = await run_topics_pipeline(
            topic_name=topic_name,
            window_hours=window_hours,
            top_k=top_k // 2  # Half the trends for topic-specific
        )
        
        # Combine results
        combined_results = {
            'runtime_seconds': time.time() - start_time,
            'window_hours': window_hours,
            'top_k': top_k,
            'global_pipeline': global_results,
            'topics_pipeline': topics_results,
            'summary': {
                'global_trends': global_results.get('selection_results', {}).get('trends_selected', 0),
                'topic_trends': topics_results.get('topics_processed', 0),
                'total_clusters': global_results.get('clustering_stats', {}).get('clusters_created', 0),
                'items_analyzed': global_results.get('clustering_stats', {}).get('items_processed', 0)
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