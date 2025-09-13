"""
Basic tests for the trender system.
Validates core functionality of the trending topics pipeline.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
import json

from newsbot.trender.cluster import ContentEmbedder, IncrementalClusterer
from newsbot.trender.score import TrendingScorer, ClusterMetrics
from newsbot.trender.selector import TrendingSelector, SelectedTrend
from newsbot.trender.topics import TopicConfig, TopicMatcher
from newsbot.trender.pipeline import TrendingPipeline


class TestContentEmbedder:
    """Test the content embedding functionality."""
    
    def test_initialization(self):
        """Test embedder initialization."""
        embedder = ContentEmbedder()
        assert embedder.vectorizer is not None
        assert embedder.vectorizer.max_features == 5000
        assert embedder.vectorizer.stop_words == 'english'
    
    def test_fit_transform(self):
        """Test fitting and transforming text content."""
        embedder = ContentEmbedder()
        
        texts = [
            "Breaking news about technology advances",
            "Sports team wins championship game",
            "Technology breakthrough in AI research",
            "Local sports event results announced"
        ]
        
        # Fit and transform
        vectors = embedder.fit_transform(texts)
        
        assert vectors is not None
        assert vectors.shape[0] == len(texts)
        assert vectors.shape[1] > 0  # Should have some features
        
        # Test similarity - tech items should be more similar
        from sklearn.metrics.pairwise import cosine_similarity
        similarities = cosine_similarity(vectors)
        
        # Items 0 and 2 (tech) should be more similar than 0 and 1 (tech vs sports)
        tech_similarity = similarities[0, 2]
        cross_similarity = similarities[0, 1]
        
        assert tech_similarity > cross_similarity
    
    def test_transform_new_content(self):
        """Test transforming new content after fitting."""
        embedder = ContentEmbedder()
        
        # Fit on some content
        fit_texts = [
            "Technology news about software development",
            "Sports championship results"
        ]
        embedder.fit_transform(fit_texts)
        
        # Transform new content
        new_texts = ["New technology breakthrough announced"]
        new_vectors = embedder.transform(new_texts)
        
        assert new_vectors is not None
        assert new_vectors.shape[0] == len(new_texts)


class TestIncrementalClusterer:
    """Test the incremental clustering functionality."""
    
    def test_initialization(self):
        """Test clusterer initialization."""
        clusterer = IncrementalClusterer()
        assert clusterer.eps == 0.3
        assert clusterer.min_samples == 2
        assert clusterer.similarity_threshold == 0.7
    
    def test_cluster_items(self):
        """Test clustering similar items together."""
        clusterer = IncrementalClusterer()
        
        # Mock items with similar content
        items = [
            {
                'id': 1,
                'title': 'AI breakthrough in machine learning',
                'content': 'Artificial intelligence research shows new capabilities in machine learning algorithms'
            },
            {
                'id': 2,
                'title': 'Machine learning advances reported',
                'content': 'New machine learning techniques demonstrate improved artificial intelligence performance'
            },
            {
                'id': 3,
                'title': 'Sports team victory',
                'content': 'Local sports team wins championship in exciting match'
            }
        ]
        
        clusters = clusterer.cluster_items(items)
        
        assert len(clusters) >= 1
        # Should group similar AI/ML items together
        ai_cluster = None
        for cluster in clusters:
            if len(cluster) >= 2:
                ai_cluster = cluster
                break
        
        if ai_cluster:
            # Check that similar items are grouped
            titles = [item['title'] for item in ai_cluster]
            assert any('AI' in title or 'machine learning' in title for title in titles)


class TestTrendingScorer:
    """Test the trending scoring functionality."""
    
    def test_initialization(self):
        """Test scorer initialization."""
        scorer = TrendingScorer()
        assert scorer.weights['viral'] == 0.3
        assert scorer.weights['freshness'] == 0.25
        assert scorer.weights['diversity'] == 0.2
        assert scorer.weights['volume'] == 0.15
        assert scorer.weights['quality'] == 0.1
    
    def test_calculate_viral_score(self):
        """Test viral score calculation."""
        scorer = TrendingScorer()
        
        # Mock cluster with engagement data
        cluster_data = {
            'items': [
                {'id': 1, 'source_id': 1},
                {'id': 2, 'source_id': 2},
                {'id': 3, 'source_id': 3}
            ]
        }
        
        # Mock global stats
        global_stats = {
            'avg_sources_per_cluster': 2.0,
            'max_sources_per_cluster': 5
        }
        
        score = scorer._calculate_viral_score(cluster_data, global_stats)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be above average (3 sources vs 2 avg)
    
    def test_calculate_freshness_score(self):
        """Test freshness score calculation."""
        scorer = TrendingScorer()
        
        # Recent cluster
        now = datetime.now(timezone.utc)
        recent_time = now - timedelta(hours=1)
        
        cluster_data = {
            'items': [
                {'id': 1, 'published_at': recent_time},
                {'id': 2, 'published_at': recent_time}
            ]
        }
        
        score = scorer._calculate_freshness_score(cluster_data, {})
        
        assert 0.0 <= score <= 1.0
        assert score > 0.8  # Should be very fresh
    
    def test_calculate_composite_score(self):
        """Test composite score calculation."""
        scorer = TrendingScorer()
        
        metrics = ClusterMetrics(
            viral_score=0.8,
            freshness_score=0.7,
            diversity_score=0.6,
            volume_score=0.5,
            quality_score=0.4
        )
        
        composite = scorer._calculate_composite_score(metrics)
        
        assert 0.0 <= composite <= 1.0
        
        # Verify weighted calculation
        expected = (
            0.8 * 0.3 +  # viral
            0.7 * 0.25 + # freshness  
            0.6 * 0.2 +  # diversity
            0.5 * 0.15 + # volume
            0.4 * 0.1    # quality
        )
        
        assert abs(composite - expected) < 0.001


class TestTrendingSelector:
    """Test the trending selection functionality."""
    
    def test_initialization(self):
        """Test selector initialization."""
        selector = TrendingSelector()
        assert selector.diversity_penalty == 0.1
    
    def test_select_global_trends(self):
        """Test global trend selection."""
        selector = TrendingSelector()
        
        # Mock scored clusters
        scored_clusters = [
            {'cluster_id': 1, 'composite_score': 0.9, 'items': [{'id': 1}]},
            {'cluster_id': 2, 'composite_score': 0.8, 'items': [{'id': 2}]},
            {'cluster_id': 3, 'composite_score': 0.7, 'items': [{'id': 3}]},
            {'cluster_id': 4, 'composite_score': 0.6, 'items': [{'id': 4}]},
        ]
        
        selected = selector.select_global_trends(scored_clusters, k=3)
        
        assert len(selected) <= 3
        assert len(selected) > 0
        
        # Should be ordered by score (with diversity adjustments)
        assert isinstance(selected[0], SelectedTrend)
        assert selected[0].final_score >= selected[1].final_score if len(selected) > 1 else True
    
    def test_diversity_penalty(self):
        """Test diversity penalty calculation."""
        selector = TrendingSelector()
        
        # Mock similar clusters (should get penalized)
        selected_trends = [
            SelectedTrend(
                cluster_id=1,
                original_score=0.9,
                final_score=0.9,
                selection_reason="High composite score",
                diversity_penalty=0.0
            )
        ]
        
        candidate = {'cluster_id': 2, 'composite_score': 0.8, 'items': [{'id': 2}]}
        
        # This is a simplified test - in reality diversity would be based on content similarity
        penalty = selector._calculate_diversity_penalty(candidate, selected_trends)
        
        assert 0.0 <= penalty <= 1.0


class TestTopicMatcher:
    """Test the topic matching functionality."""
    
    def test_initialization(self):
        """Test topic matcher initialization."""
        config = TopicConfig(
            name="technology",
            keywords=["AI", "machine learning", "software"],
            query_patterns=["technology.*breakthrough"],
            max_per_run=5,
            cadence_minutes=60
        )
        
        matcher = TopicMatcher([config])
        assert len(matcher.topics) == 1
        assert matcher.topics[0].name == "technology"
    
    def test_calculate_topic_relevance(self):
        """Test topic relevance calculation."""
        config = TopicConfig(
            name="technology",
            keywords=["AI", "machine", "software"],
            query_patterns=["tech.*news"],
            max_per_run=5,
            cadence_minutes=60
        )
        
        matcher = TopicMatcher([config])
        
        # Test with relevant content
        cluster_data = {
            'items': [
                {
                    'title': 'AI breakthrough in machine learning',
                    'content': 'New artificial intelligence software shows promise'
                }
            ]
        }
        
        relevance = matcher.calculate_topic_relevance("technology", cluster_data)
        
        assert 0.0 <= relevance <= 1.0
        assert relevance > 0.5  # Should be relevant
    
    def test_match_topics(self):
        """Test topic matching for clusters."""
        configs = [
            TopicConfig(
                name="technology",
                keywords=["AI", "software", "tech"],
                query_patterns=[],
                max_per_run=5,
                cadence_minutes=60
            ),
            TopicConfig(
                name="sports",
                keywords=["game", "team", "championship"],
                query_patterns=[],
                max_per_run=3,
                cadence_minutes=120
            )
        ]
        
        matcher = TopicMatcher(configs)
        
        clusters = [
            {
                'cluster_id': 1,
                'composite_score': 0.8,
                'items': [
                    {
                        'title': 'AI software breakthrough',
                        'content': 'New technology in artificial intelligence'
                    }
                ]
            },
            {
                'cluster_id': 2,
                'composite_score': 0.7,
                'items': [
                    {
                        'title': 'Championship game results',
                        'content': 'Local team wins important match'
                    }
                ]
            }
        ]
        
        matches = matcher.match_topics(clusters)
        
        assert len(matches) >= 1
        assert any(match['topic_name'] == 'technology' for match in matches)


class TestTrendingPipeline:
    """Test the complete trending pipeline."""
    
    @patch('newsbot.trender.pipeline.get_session')
    @patch('newsbot.core.repositories.get_recent_raw_items')
    @patch('newsbot.core.repositories.get_active_clusters')
    def test_pipeline_initialization(self, mock_clusters, mock_items, mock_session):
        """Test pipeline initialization."""
        # Mock database session
        mock_session.return_value.__aenter__.return_value = Mock()
        
        pipeline = TrendingPipeline()
        
        assert pipeline.embedder is not None
        assert pipeline.clusterer is not None
        assert pipeline.scorer is not None
        assert pipeline.selector is not None
    
    @patch('newsbot.trender.pipeline.get_session')
    @patch('newsbot.core.repositories.get_recent_raw_items')
    @patch('newsbot.core.repositories.get_active_clusters')
    async def test_run_trending_analysis(self, mock_clusters, mock_items, mock_session):
        """Test running trending analysis."""
        # Mock database session
        mock_session.return_value.__aenter__.return_value = Mock()
        
        # Mock repository responses
        mock_items.return_value = [
            {
                'id': 1,
                'title': 'Test news item',
                'content': 'This is a test news article about technology',
                'published_at': datetime.now(timezone.utc),
                'source_id': 1
            }
        ]
        
        mock_clusters.return_value = []
        
        pipeline = TrendingPipeline()
        
        # Mock the create_cluster and related functions
        with patch('newsbot.core.repositories.create_cluster', return_value=1), \
             patch('newsbot.core.repositories.add_item_to_cluster', return_value=True), \
             patch('newsbot.core.repositories.update_cluster_score', return_value=True):
            
            result = await pipeline.run_trending_analysis()
            
            assert 'stats' in result
            assert 'selected_trends' in result
            assert isinstance(result['stats'], dict)


if __name__ == '__main__':
    # Run basic tests
    pytest.main([__file__, '-v'])