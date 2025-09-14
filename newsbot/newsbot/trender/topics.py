"""Parser y runner para temas específicos.

Implementa análisis de trending topics por categorías/temas:
- Parser avanzado de queries con frases, operadores booleanos AND/OR, y NEAR/n
- Filtrado por dominios permitidos y idioma
- Control de cadencia y límites por tema
- Clustering separado por tema con topic_key
- Runner especializado para análisis por tema
"""

import asyncio
import time
import yaml
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple, Callable
from pathlib import Path
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import urlparse

from newsbot.core.db import AsyncSessionLocal
from newsbot.core.logging import get_logger
from newsbot.core.repositories import get_recent_raw_items
from newsbot.trender.cluster import IncrementalClusterer, ClusterInfo
from newsbot.trender.score import score_and_rank_clusters

logger = get_logger(__name__)

# Configuration
DEFAULT_TOPICS_CONFIG_PATH = "config/topics.yaml"
DEFAULT_WINDOW_HOURS = 24
DEFAULT_TOP_K_PER_TOPIC = 20


def compile_query(q: str) -> Callable[[str], bool]:
    """
    Return a matcher supporting "phrase", AND/OR, NEAR/n.
    
    Creates a compiled query function that can efficiently match text against
    complex query patterns including:
    - Phrase matching: "exact phrase"
    - Boolean operators: term1 AND term2, term1 OR term2
    - Proximity operators: word1 NEAR/n word2
    - Complex combinations: "phrase" AND term NEAR/3 other
    
    Args:
        q: Query string with advanced syntax
        
    Returns:
        Callable that takes text string and returns bool match result
        
    Examples:
        >>> matcher = compile_query('"machine learning" AND AI')
        >>> matcher("Advanced machine learning with AI systems")
        True
        >>> matcher("Deep learning without AI")
        False
        
        >>> proximity_matcher = compile_query('neural NEAR/3 networks')
        >>> proximity_matcher("neural network architectures")
        True
        >>> proximity_matcher("neural computing and network systems")
        False
    """
    # Create parser instance for this query
    parser = AdvancedQueryParser()
    
    # Pre-compile the query components for efficiency
    phrases, working_query = parser.extract_phrases_with_placeholders(q)
    near_ops, working_query = parser.extract_near_with_placeholders(working_query)
    working_query = ' '.join(working_query.split())
    
    def query_matcher(text: str) -> bool:
        """Compiled query matcher function."""
        # Use the main match_query method which handles all the complexity
        return parser.match_query(text, q)
    
    # Attach metadata for debugging/introspection
    query_matcher.original_query = q
    query_matcher.phrases = phrases
    query_matcher.near_operations = near_ops
    query_matcher.boolean_expression = working_query
    
    return query_matcher


@dataclass
class TopicConfig:
    """Configuración de un tema específico."""
    name: str
    topic_key: str
    queries: List[str]
    allow_domains: List[str] = None  # Si vacío, acepta cualquiera
    lang: str = None  # Filtro de idioma opcional
    cadence_minutes: int = 60
    max_posts_per_run: int = 20
    enabled: bool = True
    boost_factor: float = 1.0
    min_score: float = 0.1
    priority: float = 1.0  # Topic priority for selection
    
    def __post_init__(self):
        if self.allow_domains is None:
            self.allow_domains = []
        if not self.topic_key:
            self.topic_key = self.name.lower().replace(' ', '_')
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TopicConfig':
        """Create from dictionary."""
        return cls(
            name=data.get('name', ''),
            topic_key=data.get('topic_key', data.get('key', '')),
            queries=data.get('queries', []),
            allow_domains=data.get('allow_domains', []),
            lang=data.get('lang'),
            cadence_minutes=data.get('cadence_minutes', 60),
            max_posts_per_run=data.get('max_posts_per_run', data.get('max_per_run', 20)),
            enabled=data.get('enabled', True),
            boost_factor=data.get('boost_factor', 1.0),
            min_score=data.get('min_score', 0.1),
            priority=data.get('priority', 1.0)
        )


class AdvancedQueryParser:
    """Parser avanzado de queries con soporte para frases, booleanos y NEAR/n."""
    
    def __init__(self):
        self.phrase_re = re.compile(r'"([^"]+)"')
        self.near_re = re.compile(r'(\w+)\s+NEAR/(\d+)\s+(\w+)', re.IGNORECASE)
        self.boolean_re = re.compile(r'\b(AND|OR)\b', re.IGNORECASE)
    
    def normalize_text(self, item: Dict[str, Any]) -> str:
        """Normaliza texto como title + ' ' + summary."""
        parts = []
        if item.get('title'):
            parts.append(item['title'].strip())
        if item.get('summary'):
            parts.append(item['summary'].strip())
        return ' '.join(parts)
    
    def extract_phrases(self, query: str) -> Tuple[List[str], str]:
        """Extrae frases quoted y devuelve (frases, query_sin_frases)."""
        phrases = self.phrase_re.findall(query)
        query_without_phrases = self.phrase_re.sub(' ', query).strip()
        return phrases, query_without_phrases
    
    def extract_near_operations(self, query: str) -> Tuple[List[Tuple[str, int, str]], str]:
        """Extrae operaciones NEAR/n y devuelve (operaciones, query_sin_near)."""
        near_ops = []
        for match in self.near_re.finditer(query):
            word1, distance, word2 = match.groups()
            near_ops.append((word1, int(distance), word2))
        
        query_without_near = self.near_re.sub(' ', query).strip()
        return near_ops, query_without_near
    
    def check_phrase_match(self, text: str, phrase: str) -> bool:
        """Verifica si la frase aparece en el texto."""
        return phrase.lower() in text.lower()
    
    def check_near_match(self, text: str, word1: str, distance: int, word2: str) -> bool:
        """Check if word1 appears within 'distance' tokens of word2."""
        import re
        
        # Create word boundary patterns for more flexible matching
        def word_matches(pattern_word, text_word):
            """Check if pattern_word matches text_word with flexibility for plurals."""
            pattern_lower = pattern_word.lower()
            text_lower = text_word.lower()
            
            # Exact match
            if pattern_lower == text_lower:
                return True
            
            # Check for plural/singular variations
            if pattern_lower.endswith('s') and text_lower == pattern_lower[:-1]:
                return True  # pattern is plural, text is singular
            if text_lower.endswith('s') and pattern_lower == text_lower[:-1]:
                return True  # text is plural, pattern is singular
            
            return False
        
        words = text.lower().split()
        
        # Find positions of both words with flexible matching
        positions1 = []
        positions2 = []
        
        for i, word in enumerate(words):
            if word_matches(word1, word):
                positions1.append(i)
            if word_matches(word2, word):
                positions2.append(i)
        
        # Check if any pair is within the distance
        for i1 in positions1:
            for i2 in positions2:
                if abs(i1 - i2) <= distance:
                    return True
        return False
    
    def evaluate_boolean_expression(self, text: str, expression: str) -> bool:
        """Evaluate a simple boolean expression with AND/OR and TRUE placeholders."""
        import re
        
        # Replace TRUE placeholders with actual boolean values
        expression = expression.replace('TRUE', 'True')
        
        # Tokenize the expression
        tokens = re.split(r'\s+(AND|OR)\s+', expression, flags=re.IGNORECASE)
        
        def check_term_match(term: str, text: str) -> bool:
            """Check if a term matches in text using word boundaries."""
            if term.strip() == 'True':
                return True
            # Use word boundaries for exact word matching
            pattern = r'\b' + re.escape(term.lower()) + r'\b'
            return bool(re.search(pattern, text.lower()))
        
        if len(tokens) == 1:
            # No boolean operators
            return check_term_match(tokens[0], text)
        
        # Evaluate first term
        result = check_term_match(tokens[0], text)
        
        i = 1
        while i < len(tokens) - 1:
            operator = tokens[i].upper()
            term = tokens[i + 1].strip()
            
            term_match = check_term_match(term, text)
            
            if operator == 'AND':
                result = result and term_match
            elif operator == 'OR':
                result = result or term_match
            
            i += 2
        
        return result
    
    def match_query(self, text: str, query: str) -> bool:
        """Evalúa si el texto coincide con la query completa usando estrategia de reemplazo."""
        # Strategy: Replace matched components with placeholders and then evaluate
        working_query = query
        
        # 1. Extract and evaluate phrases, replace with TRUE/FALSE placeholders
        phrases, working_query = self.extract_phrases_with_placeholders(working_query)
        for i, phrase in enumerate(phrases):
            placeholder = f"__PHRASE_{i}__"
            if self.check_phrase_match(text, phrase):
                working_query = working_query.replace(placeholder, "TRUE")
            else:
                return False  # Short circuit on phrase failure
        
        # 2. Extract and evaluate NEAR operations, replace with TRUE/FALSE
        near_ops, working_query = self.extract_near_with_placeholders(working_query)
        for i, (word1, distance, word2) in enumerate(near_ops):
            placeholder = f"__NEAR_{i}__"
            if self.check_near_match(text, word1, distance, word2):
                working_query = working_query.replace(placeholder, "TRUE")
            else:
                return False  # Short circuit on NEAR failure
        
        # 3. Clean up whitespace
        working_query = ' '.join(working_query.split())
        
        # 4. If nothing left to evaluate
        if not working_query:
            return len(phrases) > 0 or len(near_ops) > 0
        
        # 5. Handle remaining boolean expression
        return self.evaluate_boolean_expression(text, working_query)
    
    def extract_phrases_with_placeholders(self, query: str) -> Tuple[List[str], str]:
        """Extrae frases quoted y las reemplaza con placeholders."""
        phrases = self.phrase_re.findall(query)
        working_query = query
        for i, phrase in enumerate(phrases):
            # Replace the quoted phrase with a placeholder
            pattern = f'"{re.escape(phrase)}"'
            placeholder = f"__PHRASE_{i}__"
            working_query = re.sub(pattern, placeholder, working_query)
        return phrases, working_query
    
    def extract_near_with_placeholders(self, query: str) -> Tuple[List[Tuple[str, int, str]], str]:
        """Extrae operaciones NEAR/n y las reemplaza con placeholders."""
        near_ops = []
        working_query = query
        for i, match in enumerate(self.near_re.finditer(query)):
            word1, distance, word2 = match.groups()
            near_ops.append((word1, int(distance), word2))
            # Replace NEAR operation with placeholder
            placeholder = f"__NEAR_{i}__"
            working_query = working_query.replace(match.group(0), placeholder)
        
        return near_ops, working_query


class TopicMatcher:
    """Matcher de contenido con temas específicos usando parser avanzado."""
    
    def __init__(self):
        self.query_parser = AdvancedQueryParser()
    
    def filter_by_domain(self, items: List[Dict[str, Any]], allow_domains: List[str]) -> List[Dict[str, Any]]:
        """Filtra items por dominios permitidos."""
        if not allow_domains:
            return items
        
        filtered = []
        for item in items:
            url = item.get('url', '')
            if url:
                try:
                    domain = urlparse(url).netloc.lower()
                    if any(allowed.lower() in domain for allowed in allow_domains):
                        filtered.append(item)
                except:
                    pass
            else:
                # Si no hay URL, incluir el item
                filtered.append(item)
        
        return filtered
    
    def filter_by_language(self, items: List[Dict[str, Any]], lang: str) -> List[Dict[str, Any]]:
        """Filtra items por idioma."""
        if not lang:
            return items
        
        return [item for item in items if item.get('language', '').lower() == lang.lower()]
    
    def calculate_topic_match_score(self, item: Dict[str, Any], topic_config: TopicConfig) -> float:
        """Calcula qué tan bien un item coincide con un tema usando queries avanzadas."""
        text = self.query_parser.normalize_text(item)
        if not text:
            return 0.0
        
        total_score = 0.0
        queries_matched = 0
        
        for query in topic_config.queries:
            if self.query_parser.match_query(text, query):
                queries_matched += 1
                # Agregar score base por query + boost
                total_score += 1.0
        
        if queries_matched == 0:
            return 0.0
        
        # Normalizar por número de queries y aplicar boost
        base_score = queries_matched / len(topic_config.queries)
        boosted_score = min(1.0, base_score * topic_config.boost_factor)
        
        return boosted_score
    
    def filter_items_by_topic(self, items: List[Dict[str, Any]], 
                            topic_config: TopicConfig) -> List[Tuple[Dict[str, Any], float]]:
        """Filtra items relevantes para un tema con todos los criterios."""
        # 1. Filtrar por dominio
        domain_filtered = self.filter_by_domain(items, topic_config.allow_domains)
        
        # 2. Filtrar por idioma
        lang_filtered = self.filter_by_language(domain_filtered, topic_config.lang)
        
        # 3. Aplicar matching de queries y scoring
        relevant_items = []
        for item in lang_filtered:
            match_score = self.calculate_topic_match_score(item, topic_config)
            if match_score >= topic_config.min_score:
                # Marcar item con topic_key
                item_copy = item.copy()
                item_copy['topic_key'] = topic_config.topic_key
                relevant_items.append((item_copy, match_score))
        
        # 4. Ordenar por score y respetar max_posts_per_run
        relevant_items.sort(key=lambda x: x[1], reverse=True)
        return relevant_items[:topic_config.max_posts_per_run]


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


class TopicsConfigParserNew:
    """Parser de configuración de temas desde archivos YAML - Nueva implementación."""
    
    @staticmethod
    def load_from_yaml(yaml_path: str) -> List[TopicConfig]:
        """Load topics configuration from YAML file."""
        import yaml
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            topics = []
            for topic_data in data.get('topics', []):
                topic = TopicConfig.from_dict(topic_data)
                topics.append(topic)
            
            return topics
        
        except Exception as e:
            logger.error(f"Error loading topics config from {yaml_path}: {e}")
            return []
    
    @staticmethod
    def load_from_dict(config_dict: Dict[str, Any]) -> List[TopicConfig]:
        """Load topics configuration from dictionary."""
        topics = []
        
        for topic_data in config_dict.get('topics', []):
            topic = TopicConfig.from_dict(topic_data)
            topics.append(topic)
        
        return topics


class TopicClusteringManager:
    """Gestiona clustering separado por tema con cadencia."""
    
    def __init__(self, clusterer: IncrementalClusterer):
        self.clusterer = clusterer
        self.last_run_times: Dict[str, float] = {}
    
    def should_run_topic(self, topic_config: TopicConfig) -> bool:
        """Determina si es momento de procesar un tema basado en su cadencia."""
        if not topic_config.enabled:
            return False
        
        current_time = time.time()
        last_run = self.last_run_times.get(topic_config.topic_key, 0)
        time_since_last = current_time - last_run
        
        cadence_seconds = topic_config.cadence_minutes * 60
        return time_since_last >= cadence_seconds
    
    def mark_topic_run(self, topic_key: str):
        """Marca que un tema fue procesado ahora."""
        self.last_run_times[topic_key] = time.time()
    
    async def process_topic_items(self, topic_items: List[Tuple[Dict[str, Any], float]], 
                                topic_config: TopicConfig, 
                                session) -> List[int]:
        """Procesa items de un tema específico y devuelve IDs de clusters creados/actualizados."""
        if not topic_items:
            return []
        
        logger.info(f"Processing {len(topic_items)} items for topic '{topic_config.name}'")
        
        cluster_ids = []
        
        for item, match_score in topic_items:
            try:
                # Asegurar que el item tiene el topic_key
                item['topic_key'] = topic_config.topic_key
                item['topic_match_score'] = match_score
                
                # Agregar al clusterer
                cluster_id = await self.clusterer.add_item(item, session)
                if cluster_id:
                    cluster_ids.append(cluster_id)
                    
            except Exception as e:
                logger.error(f"Error processing item for topic {topic_config.name}: {e}")
                continue
        
        self.mark_topic_run(topic_config.topic_key)
        logger.info(f"Topic '{topic_config.name}' processed. Created/updated {len(set(cluster_ids))} clusters.")
        
        return list(set(cluster_ids))


async def analyze_topic_trends_advanced(items: List[Dict[str, Any]], 
                                      topics_config: List[TopicConfig],
                                      session,
                                      clusterer: IncrementalClusterer = None,
                                      max_clusters_per_topic: int = 10) -> Dict[str, Any]:
    """
    Análisis completo de tendencias por temas con clustering separado.
    
    Args:
        items: Lista de news items para analizar
        topics_config: Configuración de temas a procesar  
        session: SQLAlchemy async session
        clusterer: Instancia del clusterer incremental
        max_clusters_per_topic: Máximo clusters a rankear por tema
    
    Returns:
        Dict con resultados por tema: clusters rankeados, métricas, etc.
    """
    logger.info(f"Starting topic trends analysis for {len(items)} items across {len(topics_config)} topics")
    
    if not clusterer:
        from .clustering import IncrementalClusterer
        clusterer = IncrementalClusterer()
    
    matcher = TopicMatcher()
    cluster_manager = TopicClusteringManager(clusterer)
    results = {}
    
    # Procesar cada tema independientemente
    for topic_config in topics_config:
        topic_result = {
            'topic_name': topic_config.name,
            'topic_key': topic_config.topic_key,
            'enabled': topic_config.enabled,
            'processed': False,
            'items_matched': 0,
            'clusters_updated': [],
            'top_clusters': [],
            'error': None
        }
        
        try:
            # Verificar cadencia
            if not cluster_manager.should_run_topic(topic_config):
                topic_result['skip_reason'] = 'cadence_not_met'
                results[topic_config.topic_key] = topic_result
                continue
            
            # Filtrar items relevantes para este tema
            topic_items = matcher.filter_items_by_topic(items, topic_config)
            topic_result['items_matched'] = len(topic_items)
            
            if not topic_items:
                topic_result['skip_reason'] = 'no_matching_items'
                cluster_manager.mark_topic_run(topic_config.topic_key)
                results[topic_config.topic_key] = topic_result
                continue
            
            # Procesar items en el clusterer (con topic_key separado)
            cluster_ids = await cluster_manager.process_topic_items(
                topic_items, topic_config, session
            )
            topic_result['clusters_updated'] = cluster_ids
            topic_result['processed'] = True
            
            # Obtener clusters top rankeados para este tema específico
            try:
                top_clusters = await score_and_rank_clusters(
                    session, 
                    k=max_clusters_per_topic,
                    topic_key=topic_config.topic_key  # Solo clusters de este tema
                )
                
                topic_result['top_clusters'] = [
                    {
                        'cluster_id': cluster.id,
                        'total_score': cluster.total_score,
                        'trend_score': cluster.trend_score,
                        'diversity_score': cluster.diversity_score,
                        'freshness_score': cluster.freshness_score,
                        'item_count': cluster.item_count,
                        'latest_item': cluster.latest_item.isoformat() if cluster.latest_item else None,
                        'sample_title': cluster.sample_title
                    }
                    for cluster in top_clusters
                ]
                
                logger.info(f"Topic '{topic_config.name}': {len(topic_items)} items → "
                          f"{len(cluster_ids)} clusters updated → "
                          f"{len(top_clusters)} top clusters ranked")
                          
            except Exception as e:
                logger.error(f"Error ranking clusters for topic {topic_config.name}: {e}")
                topic_result['error'] = f"ranking_error: {str(e)}"
        
        except Exception as e:
            logger.error(f"Error processing topic {topic_config.name}: {e}")
            topic_result['error'] = str(e)
        
        results[topic_config.topic_key] = topic_result
    
    # Resumen general
    summary = {
        'total_topics': len(topics_config),
        'topics_processed': sum(1 for r in results.values() if r['processed']),
        'total_items_matched': sum(r['items_matched'] for r in results.values()),
        'total_clusters_updated': len(set().union(*[r['clusters_updated'] for r in results.values()])),
        'topics_with_errors': sum(1 for r in results.values() if r.get('error')),
    }
    
    logger.info(f"Topic trends analysis complete: {summary}")
    
    return {
        'summary': summary,
        'topics': results,
        'timestamp': time.time()
    }