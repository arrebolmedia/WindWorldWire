"""Parser y runner para temas específicos.

Implementa análisis de trending topics por categorías/temas:
- Parser de configuración de temas desde YAML
- Matching de contenido con queries de temas
- Runner especializado para análisis por tema
- Cadence control para ejecución automática
- Integración con sistema de clustering y scoring
"""

import asyncio
import time
import yaml
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.core.db import AsyncSessionLocal
from newsbot.core.logging import get_logger
from newsbot.core.repositories import get_recent_raw_items
from newsbot.trender.cluster import cluster_recent_content
from newsbot.trender.score import score_all_clusters
from newsbot.trender.selector import select_trending_topics

logger = get_logger(__name__)

# Configuration
DEFAULT_TOPICS_CONFIG_PATH = "config/topics.yaml"
DEFAULT_WINDOW_HOURS = 24
DEFAULT_TOP_K_PER_TOPIC = 20


@dataclass
class TopicConfig:
    """Configuración de un tema específico."""
    name: str
    keywords: List[str]
    queries: List[str]
    cadence_minutes: int = 60
    max_per_run: int = 20
    enabled: bool = True
    boost_factor: float = 1.0
    min_score: float = 0.1
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TopicConfig':
        """Create from dictionary."""
        return cls(
            name=data.get('name', ''),
            keywords=data.get('keywords', []),
            queries=data.get('queries', []),
            cadence_minutes=data.get('cadence_minutes', 60),
            max_per_run=data.get('max_per_run', 20),
            enabled=data.get('enabled', True),
            boost_factor=data.get('boost_factor', 1.0),
            min_score=data.get('min_score', 0.1)
        )


class TopicMatcher:
    """Matcher de contenido con temas específicos."""
    
    def __init__(self):
        self.compiled_patterns = {}
    
    def compile_topic_patterns(self, topic_config: TopicConfig):
        """Compile regex patterns for efficient matching."""
        import re
        
        patterns = []
        
        # Keywords as word boundaries
        for keyword in topic_config.keywords:
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            patterns.append(pattern)
        
        # Query patterns (can be more complex)
        for query in topic_config.queries:
            # Simple query parsing: treat as phrase
            if ' ' in query:
                # Phrase search
                pattern = re.escape(query.lower())
            else:
                # Single word with boundaries
                pattern = r'\b' + re.escape(query.lower()) + r'\b'
            patterns.append(pattern)
        
        # Combine all patterns
        if patterns:
            combined_pattern = '|'.join(f'({p})' for p in patterns)
            self.compiled_patterns[topic_config.name] = re.compile(combined_pattern, re.IGNORECASE)
    
    def calculate_topic_match_score(self, item: Dict[str, Any], 
                                  topic_config: TopicConfig) -> float:
        """
        Calculate how well an item matches a topic.
        
        Returns score 0.0 to 1.0
        """
        if topic_config.name not in self.compiled_patterns:
            self.compile_topic_patterns(topic_config)
        
        pattern = self.compiled_patterns.get(topic_config.name)
        if not pattern:
            return 0.0
        
        # Combine text fields for matching
        text_fields = []
        
        if item.get('title'):
            text_fields.append(('title', item['title'], 2.0))  # Title has higher weight
        
        if item.get('summary'):
            text_fields.append(('summary', item['summary'], 1.0))
        
        if item.get('content'):
            # Truncate very long content
            content = item['content'][:1000]
            text_fields.append(('content', content, 0.5))
        
        if not text_fields:
            return 0.0
        
        total_score = 0.0
        total_weight = 0.0
        
        for field_name, text, weight in text_fields:
            if not text:
                continue
            
            # Count matches in this field
            matches = pattern.findall(text.lower())
            match_count = len(matches)
            
            if match_count > 0:
                # Score based on match density and field weight
                text_length = len(text.split())
                density = min(1.0, match_count / max(1, text_length / 10))  # Normalize by text length
                field_score = density * weight
                
                total_score += field_score
                total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        # Normalize score
        normalized_score = min(1.0, total_score / total_weight)
        
        # Apply topic boost factor
        boosted_score = min(1.0, normalized_score * topic_config.boost_factor)
        
        return boosted_score
    
    def filter_items_by_topic(self, items: List[Dict[str, Any]], 
                            topic_config: TopicConfig,
                            min_score: float = 0.1) -> List[Tuple[Dict[str, Any], float]]:
        """
        Filter items relevant to a topic.
        
        Returns list of (item, match_score) tuples
        """
        relevant_items = []
        
        for item in items:
            match_score = self.calculate_topic_match_score(item, topic_config)
            
            if match_score >= min_score:
                relevant_items.append((item, match_score))
        
        # Sort by match score (highest first)
        relevant_items.sort(key=lambda x: x[1], reverse=True)
        
        return relevant_items


class TopicsConfigParser:
    """Parser de configuración de temas desde YAML."""
    
    def __init__(self, config_path: str = DEFAULT_TOPICS_CONFIG_PATH):
        self.config_path = Path(config_path)
    
    def load_topics_config(self) -> List[TopicConfig]:
        """Load topics configuration from YAML file."""
        try:
            if not self.config_path.exists():
                logger.warning(f"Topics config file not found: {self.config_path}")
                return []
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            if not config_data or 'topics' not in config_data:
                logger.warning("No topics configuration found in YAML")
                return []
            
            topics = []
            
            for topic_data in config_data['topics']:
                try:
                    topic_config = TopicConfig.from_dict(topic_data)
                    if topic_config.enabled:
                        topics.append(topic_config)
                    else:
                        logger.info(f"Topic '{topic_config.name}' is disabled")
                except Exception as e:
                    logger.error(f"Error parsing topic config: {e}")
            
            logger.info(f"Loaded {len(topics)} enabled topics")
            return topics
            
        except Exception as e:
            logger.error(f"Error loading topics config: {e}")
            return []
    
    def get_topic_by_name(self, name: str) -> Optional[TopicConfig]:
        """Get specific topic configuration by name."""
        topics = self.load_topics_config()
        
        for topic in topics:
            if topic.name.lower() == name.lower():
                return topic
        
        return None


async def analyze_topic_trends(session: AsyncSession,
                             topic_config: TopicConfig,
                             window_hours: int = DEFAULT_WINDOW_HOURS) -> Dict[str, Any]:
    """
    Analyze trending topics for a specific topic category.
    
    Args:
        session: Database session
        topic_config: Topic configuration
        window_hours: Time window for analysis
        
    Returns:
        Analysis results and statistics
    """
    start_time = time.time()
    
    try:
        logger.info(f"Analyzing trends for topic: {topic_config.name}")
        
        # Get recent content
        recent_items = await get_recent_raw_items(session, hours=window_hours)
        
        if not recent_items:
            return {
                'runtime_seconds': time.time() - start_time,
                'topic_name': topic_config.name,
                'items_analyzed': 0,
                'relevant_items': 0,
                'clusters_created': 0,
                'trends_selected': 0,
                'selected_trends': []
            }
        
        # Filter items relevant to topic
        matcher = TopicMatcher()
        relevant_items_with_scores = matcher.filter_items_by_topic(
            recent_items, topic_config, topic_config.min_score
        )
        
        relevant_items = [item for item, score in relevant_items_with_scores]
        
        logger.info(
            f"Found {len(relevant_items)} relevant items for topic '{topic_config.name}' "
            f"from {len(recent_items)} total items"
        )
        
        if not relevant_items:
            return {
                'runtime_seconds': time.time() - start_time,
                'topic_name': topic_config.name,
                'items_analyzed': len(recent_items),
                'relevant_items': 0,
                'clusters_created': 0,
                'trends_selected': 0,
                'selected_trends': []
            }
        
        # Create temporary filtered dataset for clustering
        # Note: In a real implementation, you might want to create topic-specific clusters
        # For now, we'll use the general clustering but filter results
        
        # Run clustering on relevant items (simplified approach)
        # In practice, you might want to cluster only topic-relevant content
        clustering_stats = await cluster_recent_content(
            session, window_hours=window_hours, incremental=True
        )
        
        # Score clusters
        scored_clusters = await score_all_clusters(session, window_hours)
        
        if not scored_clusters:
            return {
                'runtime_seconds': time.time() - start_time,
                'topic_name': topic_config.name,
                'items_analyzed': len(recent_items),
                'relevant_items': len(relevant_items),
                'clusters_created': clustering_stats.get('clusters_created', 0),
                'trends_selected': 0,
                'selected_trends': []
            }
        
        # Select topic-specific trends
        selection_results = await select_trending_topics(
            session,
            scored_clusters,
            top_k=topic_config.max_per_run,
            topic_keywords=topic_config.keywords
        )
        
        runtime = time.time() - start_time
        
        result = {
            'runtime_seconds': runtime,
            'topic_name': topic_config.name,
            'items_analyzed': len(recent_items),
            'relevant_items': len(relevant_items),
            'clusters_created': clustering_stats.get('clusters_created', 0),
            'trends_selected': selection_results.get('trends_selected', 0),
            'selected_trends': selection_results.get('topic_trends', []),
            'clustering_stats': clustering_stats,
            'selection_stats': selection_results.get('selection_stats', {}),
            'relevance_scores': {
                'min_score': min(score for _, score in relevant_items_with_scores) if relevant_items_with_scores else 0,
                'max_score': max(score for _, score in relevant_items_with_scores) if relevant_items_with_scores else 0,
                'avg_score': sum(score for _, score in relevant_items_with_scores) / len(relevant_items_with_scores) if relevant_items_with_scores else 0
            }
        }
        
        logger.info(
            f"Topic analysis completed for '{topic_config.name}': "
            f"{result['trends_selected']} trends selected in {runtime:.2f}s"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Topic analysis failed for '{topic_config.name}': {e}")
        return {
            'runtime_seconds': time.time() - start_time,
            'topic_name': topic_config.name,
            'items_analyzed': 0,
            'relevant_items': 0,
            'clusters_created': 0,
            'trends_selected': 0,
            'selected_trends': [],
            'error': str(e)
        }


async def run_all_topics_analysis(window_hours: int = DEFAULT_WINDOW_HOURS,
                                config_path: str = DEFAULT_TOPICS_CONFIG_PATH) -> Dict[str, Any]:
    """
    Run trending analysis for all configured topics.
    
    Args:
        window_hours: Time window for analysis
        config_path: Path to topics configuration file
        
    Returns:
        Comprehensive analysis results for all topics
    """
    start_time = time.time()
    
    try:
        # Load topics configuration
        parser = TopicsConfigParser(config_path)
        topics = parser.load_topics_config()
        
        if not topics:
            logger.warning("No topics configured for analysis")
            return {
                'runtime_seconds': time.time() - start_time,
                'topics_processed': 0,
                'total_trends': 0,
                'topic_results': []
            }
        
        logger.info(f"Running analysis for {len(topics)} topics")
        
        # Analyze each topic
        topic_results = []
        total_trends = 0
        
        async with AsyncSessionLocal() as session:
            for topic_config in topics:
                try:
                    result = await analyze_topic_trends(session, topic_config, window_hours)
                    topic_results.append(result)
                    total_trends += result.get('trends_selected', 0)
                    
                except Exception as e:
                    logger.error(f"Error analyzing topic '{topic_config.name}': {e}")
                    topic_results.append({
                        'topic_name': topic_config.name,
                        'error': str(e),
                        'trends_selected': 0
                    })
        
        runtime = time.time() - start_time
        
        result = {
            'runtime_seconds': runtime,
            'topics_processed': len(topics),
            'total_trends': total_trends,
            'topic_results': topic_results,
            'summary': {
                'avg_trends_per_topic': total_trends / len(topics) if topics else 0,
                'successful_topics': sum(1 for r in topic_results if 'error' not in r),
                'failed_topics': sum(1 for r in topic_results if 'error' in r)
            }
        }
        
        logger.info(
            f"All topics analysis completed: {len(topics)} topics, "
            f"{total_trends} total trends in {runtime:.2f}s"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Topics analysis pipeline failed: {e}")
        return {
            'runtime_seconds': time.time() - start_time,
            'topics_processed': 0,
            'total_trends': 0,
            'topic_results': [],
            'error': str(e)
        }


async def run_topics_pipeline(topic_name: Optional[str] = None,
                            window_hours: int = DEFAULT_WINDOW_HOURS,
                            top_k: int = DEFAULT_TOP_K_PER_TOPIC,
                            config_path: str = DEFAULT_TOPICS_CONFIG_PATH) -> Dict[str, Any]:
    """
    Run topics-focused trending pipeline.
    
    Args:
        topic_name: Specific topic to analyze (None for all topics)
        window_hours: Time window for analysis
        top_k: Max trends per topic
        config_path: Path to topics configuration
        
    Returns:
        Pipeline results and statistics
    """
    start_time = time.time()
    
    try:
        parser = TopicsConfigParser(config_path)
        
        if topic_name:
            # Analyze specific topic
            topic_config = parser.get_topic_by_name(topic_name)
            
            if not topic_config:
                return {
                    'runtime_seconds': time.time() - start_time,
                    'topics_processed': 0,
                    'content_analyzed': 0,
                    'topic_results': [],
                    'error': f"Topic '{topic_name}' not found in configuration"
                }
            
            # Override max_per_run with top_k parameter
            topic_config.max_per_run = top_k
            
            async with AsyncSessionLocal() as session:
                result = await analyze_topic_trends(session, topic_config, window_hours)
            
            return {
                'runtime_seconds': time.time() - start_time,
                'topics_processed': 1,
                'content_analyzed': result.get('items_analyzed', 0),
                'topic_results': [result]
            }
        
        else:
            # Analyze all topics
            results = await run_all_topics_analysis(window_hours, config_path)
            
            # Adjust structure to match expected format
            return {
                'runtime_seconds': results['runtime_seconds'],
                'topics_processed': results['topics_processed'],
                'content_analyzed': sum(r.get('items_analyzed', 0) for r in results['topic_results']),
                'topic_results': results['topic_results']
            }
        
    except Exception as e:
        logger.error(f"Topics pipeline failed: {e}")
        return {
            'runtime_seconds': time.time() - start_time,
            'topics_processed': 0,
            'content_analyzed': 0,
            'topic_results': [],
            'error': str(e)
        }