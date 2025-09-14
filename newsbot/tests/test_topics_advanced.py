#!/usr/bin/env python3
"""
Tests para el sistema avanzado de análisis de temas con parser de queries sofisticado.

Cubre:
- AdvancedQueryParser (frases, booleanos, NEAR/n)
- TopicMatcher (filtros de dominio, idioma, scoring)
- TopicClusteringManager (cadencia, clustering separado)
- TopicsConfigParser (carga desde YAML/dict)
- Análisis completo de tendencias por tema

Ejecutar: python -m pytest tests/test_topics_advanced.py -v
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any
from unittest.mock import Mock, AsyncMock

from newsbot.trender.topics import (
    TopicConfig, AdvancedQueryParser, TopicMatcher,
    TopicsConfigParserNew, TopicClusteringManager,
    analyze_topic_trends_advanced, compile_query
)


class TestAdvancedQueryParser:
    """Tests para el parser avanzado de queries."""
    
    def setup_method(self):
        self.parser = AdvancedQueryParser()
    
    def test_phrase_extraction(self):
        """Test extracción de frases exactas."""
        query = 'machine "neural networks" learning AND "deep learning"'
        phrases, remaining = self.parser.extract_phrases_with_placeholders(query)
        
        assert phrases == ["neural networks", "deep learning"]
        assert "__PHRASE_0__" in remaining
        assert "__PHRASE_1__" in remaining
    
    def test_near_extraction(self):
        """Test extracción de operadores NEAR/n."""
        query = 'neural NEAR/3 network AND machine NEAR/5 learning'
        near_ops, remaining = self.parser.extract_near_with_placeholders(query)
        
        assert len(near_ops) == 2
        assert near_ops[0] == ("neural", 3, "network")
        assert near_ops[1] == ("machine", 5, "learning")
        assert "__NEAR_0__" in remaining
        assert "__NEAR_1__" in remaining
    
    def test_phrase_matching(self):
        """Test matching de frases exactas."""
        text = "Advanced machine learning algorithms and neural networks"
        
        assert self.parser.check_phrase_match(text, "machine learning")
        assert self.parser.check_phrase_match(text, "neural networks")
        assert not self.parser.check_phrase_match(text, "deep learning")
    
    def test_near_matching(self):
        """Test matching de proximidad NEAR/n."""
        text = "Advanced machine learning algorithms and neural network applications"
        tokens = text.split()
        
        # "neural" y "network" están adyacentes (distancia 1)
        assert self.parser.check_near_match(text, "neural", 2, "network")
        assert self.parser.check_near_match(text, "neural", 1, "network")
        assert not self.parser.check_near_match(text, "neural", 0, "network")  # Muy restrictivo
        
        # "machine" y "neural" están separados (distancia ~4)
        assert self.parser.check_near_match(text, "machine", 5, "neural")
        assert not self.parser.check_near_match(text, "machine", 3, "neural")
    
    def test_boolean_expressions(self):
        """Test evaluación de expresiones booleanas."""
        text = "machine learning and artificial intelligence"
        
        # AND
        assert self.parser.evaluate_boolean_expression(text, "machine AND learning")
        assert self.parser.evaluate_boolean_expression(text, "machine AND artificial")
        assert not self.parser.evaluate_boolean_expression(text, "machine AND quantum")
        
        # OR
        assert self.parser.evaluate_boolean_expression(text, "machine OR quantum")
        assert self.parser.evaluate_boolean_expression(text, "quantum OR learning")
        assert not self.parser.evaluate_boolean_expression(text, "quantum OR physics")
    
    def test_complex_query_matching(self):
        """Test matching de queries complejas."""
        text = "Advanced machine learning algorithms using neural networks for artificial intelligence"
        
        # Frase exacta
        assert self.parser.match_query(text, '"machine learning"')
        assert not self.parser.match_query(text, '"deep learning"')
        
        # Boolean
        assert self.parser.match_query(text, 'machine AND learning')
        assert self.parser.match_query(text, 'neural OR quantum')
        assert not self.parser.match_query(text, 'quantum AND physics')
        
        # NEAR
        assert self.parser.match_query(text, 'neural NEAR/3 networks')
        assert self.parser.match_query(text, 'machine NEAR/5 neural')
        assert not self.parser.match_query(text, 'machine NEAR/2 neural')
        
        # Combinado
        assert self.parser.match_query(text, '"machine learning" AND neural')
        assert self.parser.match_query(text, 'artificial AND neural NEAR/3 networks')
    
    def test_text_normalization(self):
        """Test normalización de texto title + summary."""
        item = {
            'title': 'AI Breakthrough',
            'summary': 'Machine learning advances in neural networks'
        }
        
        normalized = self.parser.normalize_text(item)
        assert normalized == "AI Breakthrough Machine learning advances in neural networks"
        
        # Solo title
        item_title_only = {'title': 'AI Breakthrough'}
        normalized = self.parser.normalize_text(item_title_only)
        assert normalized == "AI Breakthrough"
        
        # Vacío
        item_empty = {}
        normalized = self.parser.normalize_text(item_empty)
        assert normalized == ""


class TestCompileQuery:
    """Tests para la función compile_query."""
    
    def test_simple_phrase_query(self):
        """Test query simple con frase."""
        matcher = compile_query('"machine learning"')
        
        assert matcher("Advanced machine learning algorithms") is True
        assert matcher("Deep learning and AI") is False
        
        # Verificar metadata
        assert matcher.original_query == '"machine learning"'
        assert "machine learning" in matcher.phrases
    
    def test_boolean_query(self):
        """Test query con operadores booleanos."""
        and_matcher = compile_query('AI AND machine')
        
        assert and_matcher("AI and machine learning") is True
        assert and_matcher("AI without machines") is False
        assert and_matcher("machine learning only") is False
        
        or_matcher = compile_query('AI OR quantum')
        
        assert or_matcher("AI systems") is True
        assert or_matcher("quantum computing") is True
        assert or_matcher("machine learning") is False
    
    def test_near_query(self):
        """Test query con operador NEAR/n."""
        near_matcher = compile_query('neural NEAR/3 networks')
        
        assert near_matcher("neural network architectures") is True
        assert near_matcher("neural and deep networks") is True
        assert near_matcher("neural computing systems and network protocols") is False
        
        # Verificar metadata
        assert len(near_matcher.near_operations) == 1
        assert near_matcher.near_operations[0] == ("neural", 3, "networks")
    
    def test_complex_combined_query(self):
        """Test query compleja combinando múltiples operadores."""
        complex_matcher = compile_query('"machine learning" AND neural NEAR/2 networks')
        
        text1 = "Advanced machine learning with neural networks"
        text2 = "Machine learning and deep neural network architectures"
        text3 = "Deep learning without machine learning concepts"
        text4 = "Machine learning and neural processing units"
        
        assert complex_matcher(text1) is True  # Tiene frase y NEAR
        assert complex_matcher(text2) is True  # Tiene frase y NEAR
        assert complex_matcher(text3) is False  # No tiene frase exacta
        assert complex_matcher(text4) is False  # No tiene NEAR (units != networks)
    
    def test_efficiency_and_reuse(self):
        """Test que el matcher compilado es eficiente y reutilizable."""
        matcher = compile_query('AI AND "machine learning"')
        
        # Múltiples ejecuciones deberían ser consistentes
        text = "AI research in machine learning applications"
        
        for _ in range(100):
            assert matcher(text) is True
        
        # Diferentes textos
        assert matcher("AI research only") is False
        assert matcher("machine learning systems only") is False
        assert matcher("AI and machine learning systems") is True
    
    def test_empty_and_edge_cases(self):
        """Test casos edge y queries vacías."""
        # Query simple
        simple_matcher = compile_query('AI')
        assert simple_matcher("AI systems") is True
        assert simple_matcher("machine learning") is False
        
        # Query con espacios
        space_matcher = compile_query('  AI   AND   machine  ')
        assert space_matcher("AI and machine learning") is True
    
    def test_case_insensitivity(self):
        """Test que el matching es case-insensitive.""" 
        matcher = compile_query('"Machine Learning" AND ai')
        
        assert matcher("machine learning with AI") is True
        assert matcher("MACHINE LEARNING and ai systems") is True
        assert matcher("Machine Learning AND AI research") is True
    
    def test_metadata_introspection(self):
        """Test que los matchers tienen metadata correcta para debugging."""
        complex_query = '"artificial intelligence" OR ai NEAR/3 systems AND machine'
        matcher = compile_query(complex_query)
        
        # Verificar metadata
        assert matcher.original_query == complex_query
        assert hasattr(matcher, 'phrases')
        assert hasattr(matcher, 'near_operations') 
        assert hasattr(matcher, 'boolean_expression')
        
        # Contenido esperado
        assert "artificial intelligence" in matcher.phrases
        assert len([op for op in matcher.near_operations if op[1] == 3]) > 0


class TestTopicConfig:
    """Tests para configuración de temas."""
    
    def test_creation_with_defaults(self):
        """Test creación con valores por defecto."""
        config = TopicConfig(
            name="AI Research",
            topic_key="",
            queries=["machine learning"]
        )
        
        assert config.name == "AI Research"
        assert config.topic_key == "ai_research"  # Auto-generado
        assert config.allow_domains == []
        assert config.lang is None
        assert config.cadence_minutes == 60
        assert config.max_posts_per_run == 20
        assert config.enabled is True
        assert config.boost_factor == 1.0
        assert config.min_score == 0.1
    
    def test_from_dict(self):
        """Test creación desde diccionario."""
        data = {
            'name': 'Climate Change',
            'topic_key': 'climate',
            'queries': ['climate change', 'global warming'],
            'allow_domains': ['climate.org', 'nature.com'],
            'lang': 'en',
            'cadence_minutes': 30,
            'max_posts_per_run': 15,
            'enabled': False,
            'boost_factor': 1.5,
            'min_score': 0.3
        }
        
        config = TopicConfig.from_dict(data)
        
        assert config.name == 'Climate Change'
        assert config.topic_key == 'climate'
        assert config.queries == ['climate change', 'global warming']
        assert config.allow_domains == ['climate.org', 'nature.com']
        assert config.lang == 'en'
        assert config.cadence_minutes == 30
        assert config.max_posts_per_run == 15
        assert config.enabled is False
        assert config.boost_factor == 1.5
        assert config.min_score == 0.3


class TestTopicMatcher:
    """Tests para matching y filtrado de temas."""
    
    def setup_method(self):
        self.matcher = TopicMatcher()
        self.sample_items = [
            {
                'title': 'AI Breakthrough in Machine Learning',
                'summary': 'Neural networks achieve new performance records',
                'url': 'https://tech.example.com/ai-news',
                'language': 'en'
            },
            {
                'title': 'Climate Change Action Required',
                'summary': 'Urgent measures needed to combat global warming',
                'url': 'https://climate.org/urgent-action',
                'language': 'en'
            },
            {
                'title': 'Avances en Inteligencia Artificial',
                'summary': 'Sistemas IA mejoran diagnóstico médico',
                'url': 'https://tech.ejemplo.com/ia-medica',
                'language': 'es'
            }
        ]
    
    def test_domain_filtering(self):
        """Test filtrado por dominios."""
        # Sin filtro - todos los items
        filtered = self.matcher.filter_by_domain(self.sample_items, [])
        assert len(filtered) == 3
        
        # Con filtro específico
        filtered = self.matcher.filter_by_domain(self.sample_items, ['tech.example.com'])
        assert len(filtered) == 1
        assert 'tech.example.com' in filtered[0]['url']
        
        # Con múltiples dominios
        filtered = self.matcher.filter_by_domain(self.sample_items, ['tech.example.com', 'climate.org'])
        assert len(filtered) == 2
    
    def test_language_filtering(self):
        """Test filtrado por idioma."""
        # Sin filtro
        filtered = self.matcher.filter_by_language(self.sample_items, None)
        assert len(filtered) == 3
        
        # Filtro inglés
        filtered = self.matcher.filter_by_language(self.sample_items, 'en')
        assert len(filtered) == 2
        assert all(item['language'] == 'en' for item in filtered)
        
        # Filtro español
        filtered = self.matcher.filter_by_language(self.sample_items, 'es')
        assert len(filtered) == 1
        assert filtered[0]['language'] == 'es'
    
    def test_topic_match_scoring(self):
        """Test scoring de matching con temas."""
        topic_config = TopicConfig(
            name="AI Technology",
            topic_key="ai_tech",
            queries=['"machine learning"', 'AI AND neural'],
            boost_factor=1.2
        )
        
        # Item que hace match con ambas queries
        ai_item = self.sample_items[0]  # Tiene "machine learning" y "AI" + "neural"
        score = self.matcher.calculate_topic_match_score(ai_item, topic_config)
        assert score > 0.8  # Debería tener score alto con boost
        
        # Item que no hace match
        climate_item = self.sample_items[1]
        score = self.matcher.calculate_topic_match_score(climate_item, topic_config)
        assert score == 0.0
    
    def test_complete_item_filtering(self):
        """Test filtrado completo con todos los criterios."""
        topic_config = TopicConfig(
            name="AI Technology",
            topic_key="ai_tech",
            queries=['"machine learning"', 'neural'],
            allow_domains=['tech.example.com'],
            lang='en',
            min_score=0.1,
            max_posts_per_run=5
        )
        
        filtered_items = self.matcher.filter_items_by_topic(self.sample_items, topic_config)
        
        # Solo debería pasar el item de AI en inglés del dominio correcto
        assert len(filtered_items) == 1
        item, score = filtered_items[0]
        assert 'tech.example.com' in item['url']
        assert item['language'] == 'en'
        assert item['topic_key'] == 'ai_tech'
        assert score > 0.1


class TestTopicClusteringManager:
    """Tests para gestión de clustering por tema."""
    
    def setup_method(self):
        self.mock_clusterer = Mock()
        self.manager = TopicClusteringManager(self.mock_clusterer)
    
    def test_cadence_control(self):
        """Test control de cadencia de temas."""
        topic_config = TopicConfig(
            name="Test Topic",
            topic_key="test",
            queries=["test"],
            cadence_minutes=30  # 30 minutos
        )
        
        # Primera ejecución - debería ejecutar
        assert self.manager.should_run_topic(topic_config) is True
        
        # Marcar como ejecutado
        self.manager.mark_topic_run(topic_config.topic_key)
        
        # Inmediatamente después - no debería ejecutar
        assert self.manager.should_run_topic(topic_config) is False
        
        # Simular paso del tiempo
        self.manager.last_run_times[topic_config.topic_key] = time.time() - (31 * 60)  # 31 min atrás
        assert self.manager.should_run_topic(topic_config) is True
    
    def test_disabled_topic(self):
        """Test tema deshabilitado."""
        topic_config = TopicConfig(
            name="Disabled Topic",
            topic_key="disabled",
            queries=["test"],
            enabled=False
        )
        
        assert self.manager.should_run_topic(topic_config) is False
    
    @pytest.mark.asyncio
    async def test_process_topic_items(self):
        """Test procesamiento de items de tema."""
        topic_config = TopicConfig(
            name="Test Topic",
            topic_key="test_topic",
            queries=["test"]
        )
        
        topic_items = [
            ({'title': 'Test Item 1', 'content': 'test content'}, 0.8),
            ({'title': 'Test Item 2', 'content': 'test content'}, 0.6)
        ]
        
        # Mock del clusterer
        self.mock_clusterer.add_item = AsyncMock(side_effect=[101, 102])
        
        cluster_ids = await self.manager.process_topic_items(
            topic_items, topic_config, session=None
        )
        
        # Verificar que se llamó add_item para cada item
        assert self.mock_clusterer.add_item.call_count == 2
        assert cluster_ids == [101, 102]
        
        # Verificar que se marcó la ejecución
        assert topic_config.topic_key in self.manager.last_run_times


class TestTopicsConfigParser:
    """Tests para parser de configuración."""
    
    def test_load_from_dict(self):
        """Test carga desde diccionario."""
        config_dict = {
            'topics': [
                {
                    'name': 'AI Research',
                    'topic_key': 'ai',
                    'queries': ['"artificial intelligence"', 'machine learning'],
                    'allow_domains': ['tech.com'],
                    'lang': 'en',
                    'enabled': True
                },
                {
                    'name': 'Climate',
                    'topic_key': 'climate',
                    'queries': ['climate change'],
                    'enabled': False
                }
            ]
        }
        
        topics = TopicsConfigParserNew.load_from_dict(config_dict)
        
        assert len(topics) == 2
        assert topics[0].name == 'AI Research'
        assert topics[0].topic_key == 'ai'
        assert topics[0].enabled is True
        assert topics[1].name == 'Climate'
        assert topics[1].enabled is False
    
    def test_empty_config(self):
        """Test configuración vacía."""
        topics = TopicsConfigParserNew.load_from_dict({})
        assert topics == []
        
        topics = TopicsConfigParserNew.load_from_dict({'topics': []})
        assert topics == []


@pytest.mark.asyncio
class TestTopicAnalysisPipeline:
    """Tests para el pipeline completo de análisis."""
    
    def setup_method(self):
        self.sample_items = [
            {
                'title': 'Machine Learning Breakthrough',
                'summary': 'Neural networks achieve new performance in AI tasks',
                'url': 'https://tech.com/ai-breakthrough',
                'language': 'en',
                'published_at': datetime.now()
            },
            {
                'title': 'Climate Action Plan Launched', 
                'summary': 'New initiative to combat global warming',
                'url': 'https://climate.org/action-plan',
                'language': 'en',
                'published_at': datetime.now()
            }
        ]
        
        self.topics_config = [
            TopicConfig(
                name="AI Technology",
                topic_key="ai_tech",
                queries=['"machine learning"', 'neural AND networks'],
                allow_domains=['tech.com'],
                lang='en',
                cadence_minutes=30,
                max_posts_per_run=5
            ),
            TopicConfig(
                name="Climate Change",
                topic_key="climate",
                queries=['climate AND action', 'global warming'],
                allow_domains=['climate.org'],
                lang='en',
                cadence_minutes=60,
                max_posts_per_run=3
            )
        ]
    
    async def test_analyze_topic_trends_advanced(self):
        """Test análisis completo de tendencias por tema."""
        # Mock clusterer
        mock_clusterer = Mock()
        mock_clusterer.add_item = AsyncMock(return_value=1)
        
        # Mock función de scoring
        async def mock_score_and_rank_clusters(session, k=10, topic_key=None):
            # Simular clusters rankeados para el tema
            if topic_key == "ai_tech":
                return [Mock(
                    id=1, total_score=0.85, trend_score=0.4, diversity_score=0.3,
                    freshness_score=0.15, item_count=3, latest_item=datetime.now(),
                    sample_title="AI Breakthrough Story"
                )]
            return []
        
        # Patch la función en el módulo
        import newsbot.trender.topics as topics_module
        original_func = getattr(topics_module, 'score_and_rank_clusters', None)
        topics_module.score_and_rank_clusters = mock_score_and_rank_clusters
        
        try:
            results = await analyze_topic_trends_advanced(
                items=self.sample_items,
                topics_config=self.topics_config,
                session=None,
                clusterer=mock_clusterer,
                max_clusters_per_topic=5
            )
            
            # Verificar estructura de resultados
            assert 'summary' in results
            assert 'topics' in results
            assert 'timestamp' in results
            
            # Verificar summary
            summary = results['summary']
            assert summary['total_topics'] == 2
            assert summary['topics_processed'] >= 1
            
            # Verificar resultados por tema
            topics = results['topics']
            assert len(topics) == 2
            
            # El tema AI debería tener items matched
            ai_result = topics['ai_tech']
            assert ai_result['topic_name'] == "AI Technology"
            assert ai_result['items_matched'] > 0
            assert ai_result['processed'] is True
            
        finally:
            # Restaurar función original
            if original_func:
                topics_module.score_and_rank_clusters = original_func
    
    async def test_cadence_control_in_pipeline(self):
        """Test que la cadencia se respeta en el pipeline usando manager compartido."""
        # Test more isolated cadence control with manager instance
        from newsbot.trender.topics import TopicClusteringManager
        
        mock_clusterer = Mock()
        mock_clusterer.add_item = AsyncMock(return_value=1)
        
        # Crear manager compartido
        cluster_manager = TopicClusteringManager(mock_clusterer)
        
        topic_config = TopicConfig(
            name="Test Topic",
            topic_key="test",
            queries=["machine learning"],
            cadence_minutes=30
        )
        
        # Primera ejecución - debería ejecutar
        should_run_1 = cluster_manager.should_run_topic(topic_config)
        assert should_run_1 is True
        
        # Marcar como ejecutado
        cluster_manager.mark_topic_run(topic_config.topic_key)
        
        # Segunda ejecución inmediata - no debería ejecutar
        should_run_2 = cluster_manager.should_run_topic(topic_config)
        assert should_run_2 is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])