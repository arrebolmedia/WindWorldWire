#!/usr/bin/env python3
"""
Demo de funcionalidad avanzada de parsing de temas con clustering separado.

Este demo muestra el parser avanzado de queries que soporta:
- Frases exactas: "machine learning"
- Operadores booleanos: AI AND machine OR deep
- Operadores NEAR/n: neural NEAR/3 network  
- Filtros de dominio: allow_domains
- Filtros de idioma: lang
- Control de cadencia: cadence_minutes
- Clustering separado por tema: topic_key

Ejecutar: python demo_topics.py
"""

import asyncio
import time
import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Simular imports que normalmente vendrían del proyecto
class MockIncrementalClusterer:
    """Mock del clusterer para testing."""
    
    def __init__(self):
        self.clusters = {}
        self.next_id = 1
    
    async def add_item(self, item: Dict[str, Any], session) -> int:
        """Simular agregar item a cluster."""
        topic_key = item.get('topic_key', 'default')
        
        # Buscar cluster similar por topic_key y título
        title = item.get('title', '')
        for cluster_id, cluster_data in self.clusters.items():
            if (cluster_data['topic_key'] == topic_key and 
                cluster_data.get('sample_title', '').lower()[:20] == title.lower()[:20]):
                cluster_data['items'].append(item)
                return cluster_id
        
        # Crear nuevo cluster
        cluster_id = self.next_id
        self.next_id += 1
        
        self.clusters[cluster_id] = {
            'topic_key': topic_key,
            'sample_title': title,
            'items': [item],
            'created_at': time.time()
        }
        
        return cluster_id

class MockScoredCluster:
    """Mock de cluster con scores para testing."""
    
    def __init__(self, cluster_id: int, topic_key: str, sample_title: str, 
                 item_count: int, total_score: float):
        self.id = cluster_id
        self.topic_key = topic_key
        self.sample_title = sample_title
        self.item_count = item_count
        self.total_score = total_score
        self.trend_score = total_score * 0.45
        self.diversity_score = total_score * 0.35
        self.freshness_score = total_score * 0.20
        self.latest_item = datetime.now()

async def mock_score_and_rank_clusters(session, k: int = 10, topic_key: str = None) -> List[MockScoredCluster]:
    """Mock de función de ranking de clusters."""
    # Simular clusters rankeados
    clusters = []
    
    if topic_key:
        # Simular clusters específicos para el tema
        base_scores = [0.85, 0.72, 0.68, 0.45, 0.32]
        for i, score in enumerate(base_scores[:k]):
            clusters.append(MockScoredCluster(
                cluster_id=100 + i,
                topic_key=topic_key,
                sample_title=f"{topic_key.title()} trending story {i+1}",
                item_count=5 + i,
                total_score=score
            ))
    
    return clusters

# Importar las clases que implementamos
from newsbot.trender.topics import (
    TopicConfig, AdvancedQueryParser, TopicMatcher, 
    TopicsConfigParserNew, TopicClusteringManager,
    analyze_topic_trends_advanced, compile_query
)

def create_sample_items() -> List[Dict[str, Any]]:
    """Crear datos de muestra para testing."""
    return [
        {
            'title': 'Advanced Machine Learning Algorithms Show Promise',
            'summary': 'New neural network architectures demonstrate improved performance in AI tasks',
            'url': 'https://tech.example.com/ai-breakthrough',
            'language': 'en',
            'published_at': datetime.now(),
            'source': 'TechNews'
        },
        {
            'title': 'Deep Learning and Artificial Intelligence Revolution',
            'summary': 'Companies invest heavily in machine learning capabilities for automation',
            'url': 'https://business.example.com/ai-investment', 
            'language': 'en',
            'published_at': datetime.now() - timedelta(hours=2),
            'source': 'BusinessDaily'
        },
        {
            'title': 'Neural Networks Transform Healthcare Diagnosis',
            'summary': 'Medical AI systems using deep neural networks achieve breakthrough accuracy',
            'url': 'https://med.example.com/ai-diagnosis',
            'language': 'en', 
            'published_at': datetime.now() - timedelta(hours=1),
            'source': 'MedicalJournal'
        },
        {
            'title': 'Climate Change Action Plan Announced',
            'summary': 'Government reveals comprehensive strategy to combat global warming',
            'url': 'https://climate.org/action-plan',
            'language': 'en',
            'published_at': datetime.now() - timedelta(hours=3),
            'source': 'ClimateNews'
        },
        {
            'title': 'Renewable Energy Investment Soars',
            'summary': 'Solar and wind power projects receive record funding this quarter',
            'url': 'https://energy.example.com/renewable-investment',
            'language': 'en',
            'published_at': datetime.now() - timedelta(minutes=30),
            'source': 'EnergyToday'
        },
        {
            'title': 'Cryptocurrency Market Volatility Continues',
            'summary': 'Bitcoin and altcoins experience significant price fluctuations',
            'url': 'https://finance.example.com/crypto-volatility',
            'language': 'en',
            'published_at': datetime.now() - timedelta(hours=4),
            'source': 'FinanceNews'
        },
        {
            'title': 'Aplicaciones de IA en Medicina Preventiva',
            'summary': 'Sistemas inteligentes predicen enfermedades con mayor precisión',
            'url': 'https://salud.ejemplo.com/ia-medicina',
            'language': 'es',
            'published_at': datetime.now() - timedelta(hours=1),
            'source': 'SaludDigital'
        }
    ]

def create_sample_topics() -> List[TopicConfig]:
    """Crear configuraciones de temas de muestra."""
    return [
        TopicConfig(
            name="Artificial Intelligence",
            topic_key="ai_tech",
            queries=[
                '"machine learning"',  # Frase exacta
                'AI AND neural',  # Boolean AND
                'artificial NEAR/2 intelligence',  # Proximidad
                'deep OR neural'  # Boolean OR
            ],
            allow_domains=['tech.example.com', 'med.example.com'],
            lang='en',
            cadence_minutes=30,
            max_posts_per_run=5,
            boost_factor=1.2,
            min_score=0.3
        ),
        TopicConfig(
            name="Climate & Energy",
            topic_key="climate_energy", 
            queries=[
                '"climate change"',
                'renewable AND energy',
                'solar OR wind',
                'carbon NEAR/3 emissions'
            ],
            allow_domains=['climate.org', 'energy.example.com'],
            lang='en',
            cadence_minutes=60,
            max_posts_per_run=3,
            boost_factor=1.0,
            min_score=0.2
        ),
        TopicConfig(
            name="Medicina IA",
            topic_key="medicina_ia",
            queries=[
                '"inteligencia artificial"',
                'IA AND medicina',
                'sistemas NEAR/2 inteligentes'
            ],
            allow_domains=['salud.ejemplo.com'],
            lang='es',
            cadence_minutes=45,
            max_posts_per_run=4,
            boost_factor=1.1,
            min_score=0.25
        )
    ]

async def demo_compile_query():
    """Demostrar la función compile_query que retorna matchers compilados."""
    print("\n" + "="*60)
    print("DEMO: Compile Query Function")
    print("="*60)
    
    # Texto de prueba
    test_texts = [
        "Advanced machine learning algorithms and AI systems",
        "Neural networks for deep learning applications", 
        "Artificial intelligence in machine learning research",
        "Quantum computing and neural network architectures",
        "Deep learning without machine learning foundations"
    ]
    
    # Queries de prueba
    test_queries = [
        '"machine learning"',                    # Frase exacta
        'AI AND neural',                         # Boolean AND
        'machine OR quantum',                    # Boolean OR
        'neural NEAR/3 networks',                # Proximidad
        '"machine learning" AND AI',             # Frase + Boolean
        'neural NEAR/2 networks OR quantum'     # Proximidad + Boolean
    ]
    
    print("Compiling and testing query matchers:\n")
    
    for query in test_queries:
        print(f"Query: {query}")
        
        # Compilar query
        matcher = compile_query(query)
        
        # Mostrar metadata
        print(f"  Phrases: {getattr(matcher, 'phrases', [])}")
        print(f"  NEAR ops: {getattr(matcher, 'near_operations', [])}")
        print(f"  Boolean expr: {getattr(matcher, 'boolean_expression', 'N/A')}")
        
        # Probar contra cada texto
        print("  Results:")
        for i, text in enumerate(test_texts):
            result = matcher(text)
            status = "✓" if result else "✗"
            print(f"    {status} Text {i+1}: {text[:50]}...")
        
        print()

async def demo_query_parser():
    """Demostrar el parser avanzado de queries."""
    print("\n" + "="*60)
    print("DEMO: Advanced Query Parser")
    print("="*60)
    
    parser = AdvancedQueryParser()
    
    test_text = "Advanced machine learning algorithms and artificial intelligence neural networks"
    
    test_queries = [
        '"machine learning"',  # Frase exacta
        'machine AND learning',  # Boolean AND
        'AI OR artificial',  # Boolean OR  
        'neural NEAR/2 networks',  # Proximidad
        'deep AND neural OR machine',  # Combinado
        '"neural networks" AND artificial'  # Frase + Boolean
    ]
    
    print(f"Texto de prueba: '{test_text}'\n")
    
    for query in test_queries:
        result = parser.match_query(test_text, query)
        print(f"Query: {query:30} → {'✓ MATCH' if result else '✗ NO MATCH'}")

async def demo_topic_matching():
    """Demostrar matching de items con temas."""
    print("\n" + "="*60)
    print("DEMO: Topic Matching & Filtering")
    print("="*60)
    
    items = create_sample_items()
    topics = create_sample_topics()
    matcher = TopicMatcher()
    
    for topic in topics:
        print(f"\n--- Topic: {topic.name} ---")
        print(f"Queries: {topic.queries}")
        print(f"Domains: {topic.allow_domains}")
        print(f"Language: {topic.lang}")
        
        matched_items = matcher.filter_items_by_topic(items, topic)
        
        print(f"Matched items: {len(matched_items)}")
        
        for item, score in matched_items:
            print(f"  • {item['title'][:50]}... (score: {score:.2f})")

async def demo_clustering_management():
    """Demostrar gestión de clustering por tema."""
    print("\n" + "="*60)
    print("DEMO: Topic-based Clustering Management")
    print("="*60)
    
    # Mock clusterer
    clusterer = MockIncrementalClusterer()
    cluster_manager = TopicClusteringManager(clusterer)
    
    items = create_sample_items()
    topics = create_sample_topics()
    matcher = TopicMatcher()
    
    # Simular procesamiento de temas con cadencia
    for topic in topics:
        print(f"\n--- Processing Topic: {topic.name} ---")
        
        # Verificar cadencia (primera vez siempre debería ejecutar)
        should_run = cluster_manager.should_run_topic(topic)
        print(f"Should run: {should_run}")
        
        if should_run:
            # Obtener items relevantes
            topic_items = matcher.filter_items_by_topic(items, topic)
            print(f"Relevant items: {len(topic_items)}")
            
            # Procesar en el clusterer
            cluster_ids = await cluster_manager.process_topic_items(
                topic_items, topic, session=None
            )
            print(f"Clusters updated: {cluster_ids}")
    
    # Mostrar estado del clusterer
    print(f"\nClustering state:")
    print(f"Total clusters: {len(clusterer.clusters)}")
    for cluster_id, cluster_data in clusterer.clusters.items():
        topic_key = cluster_data['topic_key']
        item_count = len(cluster_data['items'])
        title = cluster_data['sample_title'][:40]
        print(f"  Cluster {cluster_id} ({topic_key}): {item_count} items - '{title}...'")

async def demo_full_pipeline():
    """Demostrar pipeline completo de análisis de temas."""
    print("\n" + "="*60)
    print("DEMO: Complete Topic Analysis Pipeline")
    print("="*60)
    
    # Monkey patch la función de scoring para testing
    import newsbot.trender.topics as topics_module
    topics_module.score_and_rank_clusters = mock_score_and_rank_clusters
    
    items = create_sample_items()
    topics_config = create_sample_topics()
    
    # Ejecutar análisis completo
    results = await analyze_topic_trends_advanced(
        items=items,
        topics_config=topics_config,
        session=None,  # Mock session
        clusterer=MockIncrementalClusterer(),
        max_clusters_per_topic=5
    )
    
    # Mostrar resultados
    print(f"\nAnalysis Results:")
    print(f"Summary: {results['summary']}")
    
    print(f"\nTopics processed:")
    for topic_key, topic_result in results['topics'].items():
        print(f"\n--- {topic_result['topic_name']} ---")
        print(f"  Processed: {topic_result['processed']}")
        print(f"  Items matched: {topic_result['items_matched']}")
        print(f"  Clusters updated: {len(topic_result['clusters_updated'])}")
        print(f"  Top clusters: {len(topic_result['top_clusters'])}")
        
        if topic_result.get('error'):
            print(f"  ERROR: {topic_result['error']}")
        
        if topic_result['top_clusters']:
            print(f"  Best cluster: '{topic_result['top_clusters'][0]['sample_title']}' "
                  f"(score: {topic_result['top_clusters'][0]['total_score']:.3f})")

async def demo_yaml_config():
    """Demostrar carga de configuración desde YAML."""
    print("\n" + "="*60)
    print("DEMO: YAML Configuration Loading")
    print("="*60)
    
    # Crear ejemplo de configuración YAML
    yaml_config = {
        'topics': [
            {
                'name': 'AI & Machine Learning',
                'topic_key': 'ai_ml',
                'queries': [
                    '"artificial intelligence"',
                    'machine AND learning',
                    'neural NEAR/3 network'
                ],
                'allow_domains': ['tech.com', 'ai.org'],
                'lang': 'en',
                'cadence_minutes': 30,
                'max_posts_per_run': 10,
                'boost_factor': 1.5,
                'min_score': 0.3,
                'enabled': True
            },
            {
                'name': 'Cryptocurrency',
                'topic_key': 'crypto',
                'queries': [
                    'bitcoin OR cryptocurrency',
                    '"digital currency"',
                    'blockchain AND technology'
                ],
                'allow_domains': ['finance.com'],
                'lang': 'en', 
                'cadence_minutes': 15,
                'max_posts_per_run': 5,
                'boost_factor': 1.0,
                'min_score': 0.2,
                'enabled': False  # Disabled topic
            }
        ]
    }
    
    # Cargar usando el parser
    topics = TopicsConfigParserNew.load_from_dict(yaml_config)
    
    print(f"Loaded {len(topics)} topics from config:")
    for topic in topics:
        print(f"\n--- {topic.name} ---")
        print(f"  Key: {topic.topic_key}")
        print(f"  Enabled: {topic.enabled}")
        print(f"  Queries: {topic.queries}")
        print(f"  Domains: {topic.allow_domains}")
        print(f"  Language: {topic.lang}")
        print(f"  Cadence: {topic.cadence_minutes}min")
        print(f"  Max posts: {topic.max_posts_per_run}")
        print(f"  Boost: {topic.boost_factor}")

async def main():
    """Ejecutar todos los demos."""
    print("🚀 Advanced Topic Parsing & Clustering Demo")
    print("This demo showcases the advanced query parser with:")
    print("  • Phrase matching: \"exact phrase\"")
    print("  • Boolean operators: AND, OR") 
    print("  • Proximity operators: NEAR/n")
    print("  • Domain filtering")
    print("  • Language filtering")
    print("  • Cadence control")
    print("  • Topic-separated clustering")
    
    try:
        await demo_compile_query()
        await demo_query_parser()
        await demo_topic_matching()
        await demo_clustering_management()
        await demo_full_pipeline()
        await demo_yaml_config()
        
        print("\n" + "="*60)
        print("✅ All demos completed successfully!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())