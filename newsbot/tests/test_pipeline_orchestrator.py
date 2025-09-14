"""Tests para el pipeline orquestador."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from newsbot.trender.pipeline import run_trending, run_topics
from newsbot.trender.selector_final import Selection, SelectedPick
from newsbot.trender.score import ClusterMetrics


@pytest.fixture
def mock_raw_items():
    """Mock raw items data."""
    return [
        {
            'id': 1,
            'title': 'Taiwan military drills announced',
            'summary': 'Taiwan announces new military exercises in response to regional tensions.',
            'url': 'https://reuters.com/taiwan-drills',
            'published_at': '2025-09-12T10:00:00Z',
            'lang': 'en'
        },
        {
            'id': 2,
            'title': 'AI startup raises $100M in funding',
            'summary': 'Technology company secures major investment for machine learning research.',
            'url': 'https://techcrunch.com/ai-funding',
            'published_at': '2025-09-12T09:30:00Z',
            'lang': 'en'
        },
        {
            'id': 3,
            'title': 'Climate summit reaches new agreement',
            'summary': 'World leaders agree on new climate action framework.',
            'url': 'https://bbc.com/climate-summit',
            'published_at': '2025-09-12T08:15:00Z',
            'lang': 'en'
        }
    ]


@pytest.fixture
def mock_cluster_metrics():
    """Mock cluster metrics data."""
    return [
        ClusterMetrics(
            cluster_id=101, viral_score=0.9, freshness_score=0.8,
            diversity_score=0.7, volume_score=0.8, quality_score=0.9,
            composite_score=0.92, item_count=12, avg_age_hours=1.5,
            unique_sources=8, unique_domains=5
        ),
        ClusterMetrics(
            cluster_id=102, viral_score=0.8, freshness_score=0.9,
            diversity_score=0.8, volume_score=0.7, quality_score=0.8,
            composite_score=0.85, item_count=8, avg_age_hours=2.0,
            unique_sources=6, unique_domains=4
        )
    ]


@pytest.fixture
def mock_selection():
    """Mock selection result."""
    return Selection(
        global_picks=[
            SelectedPick(101, 0.92, 0.92, 'global', rank=1),
            SelectedPick(102, 0.85, 0.85, 'global', rank=2)
        ],
        topic_picks=[
            SelectedPick(101, 0.92, 0.828, 'topic', 'taiwan_seguridad', 0.9, rank=1)
        ]
    )


@pytest.mark.asyncio
async def test_run_trending_success(mock_raw_items, mock_cluster_metrics, mock_selection):
    """Test successful run_trending execution."""
    
    with patch('newsbot.trender.pipeline.get_recent_raw_items', return_value=mock_raw_items), \
         patch('newsbot.trender.pipeline.cluster_recent_items', return_value={'stats': {'new_clusters': 2}}), \
         patch('newsbot.trender.pipeline.score_all_clusters', return_value=mock_cluster_metrics), \
         patch('newsbot.trender.pipeline.run_final_selection', return_value=mock_selection):
        
        result = await run_trending(window_hours=24, k_global=10)
        
        assert isinstance(result, Selection)
        assert len(result.global_picks) == 2
        assert len(result.topic_picks) == 1
        assert result.total_picks == 3


@pytest.mark.asyncio 
async def test_run_trending_no_data():
    """Test run_trending with no data."""
    
    with patch('newsbot.trender.pipeline.get_recent_raw_items', return_value=[]):
        
        result = await run_trending(window_hours=24, k_global=10)
        
        assert isinstance(result, Selection)
        assert len(result.global_picks) == 0
        assert len(result.topic_picks) == 0
        assert result.total_picks == 0


@pytest.mark.asyncio
async def test_run_trending_error_handling():
    """Test run_trending error handling."""
    
    with patch('newsbot.trender.pipeline.get_recent_raw_items', side_effect=Exception("Database error")):
        
        result = await run_trending(window_hours=24, k_global=10)
        
        # Should return empty selection on error
        assert isinstance(result, Selection)
        assert result.total_picks == 0


@pytest.mark.asyncio
async def test_run_topics_success(mock_raw_items, mock_cluster_metrics, mock_selection):
    """Test successful run_topics execution."""
    
    # Mock topics configuration
    mock_topics = [
        MagicMock(
            topic_key='taiwan_seguridad',
            name='Taiwan Security',
            enabled=True,
            queries=['"Taiwan"'],
            priority=0.9
        ),
        MagicMock(
            topic_key='ai_tech',
            name='AI Technology', 
            enabled=True,
            queries=['"AI"', '"machine learning"'],
            priority=0.7
        )
    ]
    
    with patch('newsbot.trender.pipeline.TopicsConfigParserNew.load_from_yaml', return_value=mock_topics), \
         patch('newsbot.trender.pipeline.get_recent_raw_items', return_value=mock_raw_items), \
         patch('newsbot.trender.pipeline.cluster_recent_items', return_value={'stats': {'new_clusters': 1}}), \
         patch('newsbot.trender.pipeline.score_all_clusters', return_value=mock_cluster_metrics), \
         patch('newsbot.trender.pipeline.run_final_selection', return_value=mock_selection), \
         patch('newsbot.trender.topics.TopicMatcher') as mock_matcher_class:
        
        # Mock the matcher instances
        mock_matcher = mock_matcher_class.return_value
        mock_matcher.match_item.return_value = {'is_match': True, 'score': 0.8}
        
        result = await run_topics(window_hours=24)
        
        assert isinstance(result, dict)
        assert len(result) == 2  # Two topics processed
        assert 'taiwan_seguridad' in result
        assert 'ai_tech' in result
        
        for topic_key, selection in result.items():
            assert isinstance(selection, Selection)


@pytest.mark.asyncio
async def test_run_topics_no_enabled_topics():
    """Test run_topics with no enabled topics."""
    
    with patch('newsbot.trender.pipeline.TopicsConfigParserNew.load_from_yaml', return_value=[]):
        
        result = await run_topics(window_hours=24)
        
        assert isinstance(result, dict)
        assert len(result) == 0


@pytest.mark.asyncio
async def test_run_topics_no_matching_items(mock_raw_items):
    """Test run_topics when no items match any topic."""
    
    mock_topics = [
        MagicMock(
            topic_key='crypto',
            name='Cryptocurrency',
            enabled=True,
            queries=['"Bitcoin"'],
            priority=0.5
        )
    ]
    
    with patch('newsbot.trender.pipeline.TopicsConfigParserNew.load_from_yaml', return_value=mock_topics), \
         patch('newsbot.trender.pipeline.get_recent_raw_items', return_value=mock_raw_items), \
         patch('newsbot.trender.topics.TopicMatcher') as mock_matcher_class:
        
        # Mock matcher to return no matches
        mock_matcher = mock_matcher_class.return_value
        mock_matcher.match_item.return_value = {'is_match': False, 'score': 0.0}
        
        result = await run_topics(window_hours=24)
        
        assert isinstance(result, dict)
        assert 'crypto' in result
        
        # Should have empty selection for the topic
        crypto_selection = result['crypto']
        assert isinstance(crypto_selection, Selection)
        assert crypto_selection.total_picks == 0


@pytest.mark.asyncio
async def test_run_topics_error_handling():
    """Test run_topics error handling."""
    
    with patch('newsbot.trender.pipeline.TopicsConfigParserNew.load_from_yaml', side_effect=Exception("Config error")):
        
        result = await run_topics(window_hours=24)
        
        # Should return empty dict on error
        assert isinstance(result, dict)
        assert len(result) == 0


def test_pipeline_integration():
    """Test that both pipeline functions can be imported and called."""
    
    # Test imports work
    from newsbot.trender.pipeline import run_trending, run_topics
    
    # Test functions are callable
    assert callable(run_trending)
    assert callable(run_topics)
    
    # Test function signatures
    import inspect
    
    trending_sig = inspect.signature(run_trending)
    assert 'window_hours' in trending_sig.parameters
    assert 'k_global' in trending_sig.parameters
    
    topics_sig = inspect.signature(run_topics)
    assert 'window_hours' in topics_sig.parameters


if __name__ == "__main__":
    # Run tests manually
    async def run_tests():
        print("Running pipeline orchestrator tests...")
        
        # Test imports
        test_pipeline_integration()
        print("✅ Integration test passed")
        
        # Test basic functionality with mocked data
        from unittest.mock import MagicMock
        
        mock_items = [
            {'id': 1, 'title': 'Test news', 'summary': 'Test summary'}
        ]
        
        mock_metrics = [
            ClusterMetrics(1, 0.8, 0.9, 0.7, 0.6, 0.8, 0.85, 5, 2.0, 3, 2)
        ]
        
        mock_sel = Selection(
            global_picks=[SelectedPick(1, 0.85, 0.85, 'global')],
            topic_picks=[]
        )
        
        await test_run_trending_no_data()
        print("✅ No data test passed")
        
        await test_run_topics_no_enabled_topics()
        print("✅ No topics test passed")
        
        print("🎉 All manual tests passed!")
    
    asyncio.run(run_tests())