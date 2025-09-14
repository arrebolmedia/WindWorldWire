"""
Tests para las funciones de scoring de trender con dependencias reales.
"""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import asyncio

# Importar directamente las funciones de scoring
from newsbot.trender.score import (
    trend_spike_score,
    domain_diversity_score, 
    freshness_score,
    total_score,
    persist_cluster_scores,
    rank_clusters,
    score_and_rank_clusters,
    gini,
    HistoricalMetricsCache
)


class TestScoreFunctions:
    """Tests para las funciones básicas de scoring."""
    
    def test_gini_coefficient(self):
        """Test del cálculo del coeficiente de Gini."""
        # Distribución perfectamente igual
        assert gini([1, 1, 1, 1]) == 0.0
        
        # Distribución perfectamente desigual
        result = gini([0, 0, 0, 10])
        assert result > 0.5  # Alta desigualdad
        
        # Caso vacío
        assert gini([]) == 0.0
        assert gini([0, 0, 0]) == 0.0
    
    def test_trend_spike_score_no_history(self):
        """Test de trend_spike_score sin historia."""
        # Sin historia, items_count >= 2 -> 1.0
        cluster = {'items_count': 3}
        assert trend_spike_score(cluster) == 1.0
        
        # Sin historia, items_count < 2 -> 0.0
        cluster = {'items_count': 1}
        assert trend_spike_score(cluster) == 0.0
        
        # Sin items_count
        cluster = {}
        assert trend_spike_score(cluster) == 0.0
    
    def test_trend_spike_score_with_history(self):
        """Test de trend_spike_score con historia."""
        cluster = {'items_count': 10}
        history = [5, 5, 5, 5, 5, 5, 5]  # Media = 5, std > 0
        
        score = trend_spike_score(cluster, history)
        assert 0.5 < score <= 1.0  # Spike positivo
        
        # Caso donde el count actual es menor que la media
        cluster = {'items_count': 2}
        score = trend_spike_score(cluster, history)
        assert 0.0 <= score < 0.5  # Spike negativo
    
    def test_domain_diversity_score(self):
        """Test de domain_diversity_score."""
        # Alta diversidad (distribución uniforme)
        cluster = {'domains': {'a.com': 1, 'b.com': 1, 'c.com': 1}}
        score = domain_diversity_score(cluster)
        assert score > 0.8  # Alta diversidad
        
        # Baja diversidad (un dominio domina)
        cluster = {'domains': {'a.com': 10, 'b.com': 1}}
        score = domain_diversity_score(cluster)
        assert score < 0.8  # Baja diversidad
        
        # Sin dominios
        cluster = {'domains': {}}
        assert domain_diversity_score(cluster) == 0.0
        
        cluster = {}
        assert domain_diversity_score(cluster) == 0.0
    
    def test_freshness_score(self):
        """Test de freshness_score."""
        now = datetime.now(timezone.utc)
        
        # Item muy reciente
        recent_item = {
            'published_at': now - timedelta(minutes=30)
        }
        cluster = {'items': [recent_item]}
        
        score = freshness_score(cluster, now, tau_hours=3.0)
        assert score > 0.8  # Muy fresco (ajustado expectativa)
        
        # Item viejo
        old_item = {
            'published_at': now - timedelta(hours=12)
        }
        cluster = {'items': [old_item]}
        
        score = freshness_score(cluster, now, tau_hours=3.0)
        assert score < 0.1  # Poco fresco
        
        # Sin items
        cluster = {'items': []}
        assert freshness_score(cluster, now) == 0.0
    
    def test_total_score(self):
        """Test de total_score con ponderación correcta."""
        # Pesos: 0.45*trend + 0.35*diversity + 0.20*freshness
        score = total_score(1.0, 1.0, 1.0)
        assert score == 1.0
        
        score = total_score(0.0, 0.0, 0.0)
        assert score == 0.0
        
        # Test ponderación
        score = total_score(1.0, 0.0, 0.0)
        assert score == 0.45
        
        score = total_score(0.0, 1.0, 0.0)
        assert score == 0.35
        
        score = total_score(0.0, 0.0, 1.0)
        assert score == 0.20
    
    def test_persist_cluster_scores(self):
        """Test de persistencia de scores en cluster."""
        cluster = {'id': 1}
        persist_cluster_scores(cluster, 0.8, 0.6, 0.4, 0.65)
        
        assert cluster['score_trend'] == 0.8
        assert cluster['score_diversity'] == 0.6
        assert cluster['score_freshness'] == 0.4
        assert cluster['score_total'] == 0.65
    
    def test_rank_clusters(self):
        """Test de ranking de clusters."""
        clusters = [
            {'id': 1, 'status': 'open', 'score_total': 0.8},
            {'id': 2, 'status': 'open', 'score_total': 0.9},
            {'id': 3, 'status': 'closed', 'score_total': 0.95},  # Cerrado
            {'id': 4, 'status': 'open', 'score_total': 0.7},
        ]
        
        # Top 2 clusters abiertos
        ranked = rank_clusters(clusters, k=2)
        
        assert len(ranked) == 2
        assert ranked[0]['id'] == 2  # Score más alto (0.9)
        assert ranked[1]['id'] == 1  # Segundo más alto (0.8)
        
        # Verifica que no incluye el cluster cerrado
        assert all(c['status'] == 'open' for c in ranked)


class TestHistoricalMetricsCache:
    """Tests para el cache de métricas históricas."""
    
    @patch('redis.from_url')
    def test_redis_cache_operations(self, mock_redis):
        """Test operaciones con Redis disponible."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True
        
        cache = HistoricalMetricsCache()
        
        # Test add_count
        cache.add_count(123, 5)
        mock_client.rpush.assert_called_with('cluster_history:123', 5)
        mock_client.ltrim.assert_called_with('cluster_history:123', -30, -1)
        mock_client.expire.assert_called()
        
        # Test get_history
        mock_client.lrange.return_value = ['1', '2', '3']
        history = cache.get_history(123)
        assert history == [1, 2, 3]
    
    @patch('redis.from_url')
    def test_memory_cache_fallback(self, mock_redis):
        """Test fallback a cache en memoria cuando Redis no está disponible."""
        mock_redis.side_effect = Exception("Redis not available")
        
        cache = HistoricalMetricsCache()
        assert cache.redis is None
        
        # Operaciones en memoria
        cache.add_count(123, 5)
        cache.add_count(123, 10)
        
        history = cache.get_history(123)
        assert history == [5, 10]
        
        # Test límite de historia
        for i in range(35):  # Más del límite (30)
            cache.add_count(456, i)
        
        history = cache.get_history(456)
        assert len(history) == 30  # Máximo 30
        assert history[0] == 5  # Primeros 5 fueron eliminados


class TestIntegration:
    """Tests de integración con dependencias reales."""
    
    def test_score_and_rank_clusters_complete_with_real_deps(self):
        """Test completo de score_and_rank_clusters usando dependencias reales."""
        now = datetime.now(timezone.utc)
        
        clusters = [
            {
                'id': 1,
                'status': 'open',
                'items_count': 5,
                'domains': {'a.com': 2, 'b.com': 3},
                'items': [
                    {'published_at': now - timedelta(hours=1)},
                    {'published_at': now - timedelta(hours=2)},
                ]
            },
            {
                'id': 2,
                'status': 'open', 
                'items_count': 10,
                'domains': {'c.com': 5, 'd.com': 5},
                'items': [
                    {'published_at': now - timedelta(minutes=30)},
                ]
            }
        ]
        
        # Con historia mockada
        historic_counts = {
            1: [3, 3, 3, 3, 3, 3, 3],  # Media = 3, actual = 5 (spike)
            2: [8, 8, 8, 8, 8, 8, 8],  # Media = 8, actual = 10 (spike pequeño)
        }
        
        # Test con cache real (fallback a memoria)
        with patch('redis.from_url') as mock_redis:
            mock_redis.side_effect = Exception("Redis not available")
            
            ranked = score_and_rank_clusters(
                clusters, 
                historic_counts_map=historic_counts,
                now=now,
                k=10
            )
        
        # Verifica que se calcularon los scores
        assert all('score_total' in c for c in clusters)
        assert all('score_trend' in c for c in clusters)
        assert all('score_diversity' in c for c in clusters)
        assert all('score_freshness' in c for c in clusters)
        
        # Verifica ranking
        assert len(ranked) <= 10
        assert all(c['status'] == 'open' for c in ranked)
        
        # Scores deben estar en [0, 1]
        for cluster in clusters:
            assert 0 <= cluster['score_total'] <= 1
            assert 0 <= cluster['score_trend'] <= 1
            assert 0 <= cluster['score_diversity'] <= 1
            assert 0 <= cluster['score_freshness'] <= 1
    
    @pytest.mark.asyncio
    @patch('newsbot.trender.score.AsyncSessionLocal')
    async def test_update_cluster_scores_in_db(self, mock_session_local):
        """Test actualización de scores en base de datos."""
        from newsbot.trender.score import update_cluster_scores_in_db
        
        # Mock de la sesión de base de datos
        mock_session = MagicMock()
        mock_session.execute = MagicMock(return_value=asyncio.Future())
        mock_session.execute.return_value.set_result(None)
        mock_session.commit = MagicMock(return_value=asyncio.Future())
        mock_session.commit.return_value.set_result(None)
        mock_session_local.return_value.__aenter__.return_value = mock_session
        
        clusters = [
            {
                'id': 1,
                'score_trend': 0.8,
                'score_diversity': 0.6,
                'score_freshness': 0.4,
                'score_total': 0.65
            },
            {
                'id': 2,
                'score_trend': 0.9,
                'score_diversity': 0.7,
                'score_freshness': 0.5,
                'score_total': 0.75
            }
        ]
        
        await update_cluster_scores_in_db(mock_session, clusters)
        
        # Verifica que se ejecutaron las actualizaciones
        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])