"""Tests for the final selector module."""

import pytest
import numpy as np
from newsbot.trender.selector_final import PickSelector, Selection, SelectedPick
from newsbot.trender.score import ClusterMetrics
from newsbot.trender.topics import TopicConfig


def test_centroid_similarity():
    """Test centroid similarity calculation."""
    selector = PickSelector()
    
    # Identical vectors
    centroids = {
        1: np.array([1.0, 0.0, 0.0]),
        2: np.array([1.0, 0.0, 0.0])
    }
    similarity = selector.calculate_centroid_similarity(1, 2, centroids)
    assert similarity == 1.0
    
    # Orthogonal vectors
    centroids = {
        1: np.array([1.0, 0.0, 0.0]),
        2: np.array([0.0, 1.0, 0.0])
    }
    similarity = selector.calculate_centroid_similarity(1, 2, centroids)
    assert similarity == 0.0
    
    # Similar but not identical
    centroids = {
        1: np.array([1.0, 0.1, 0.0]),
        2: np.array([1.0, 0.2, 0.0])
    }
    similarity = selector.calculate_centroid_similarity(1, 2, centroids)
    assert 0.9 < similarity < 1.0


def test_global_selection():
    """Test global pick selection."""
    selector = PickSelector()
    
    clusters = [
        ClusterMetrics(1, 0.8, 0.9, 0.7, 0.6, 0.8, 0.95, 5, 2.0, 3, 2),
        ClusterMetrics(2, 0.7, 0.8, 0.6, 0.7, 0.9, 0.85, 8, 4.0, 4, 3),
        ClusterMetrics(3, 0.6, 0.7, 0.5, 0.5, 0.7, 0.75, 3, 6.0, 2, 2)
    ]
    
    sources_config = {'k_global': 50, 'max_posts_per_run': 2}
    
    picks = selector.select_global_picks(clusters, sources_config)
    
    assert len(picks) == 2  # Limited by max_posts_per_run
    assert picks[0].cluster_id == 1  # Highest score
    assert picks[1].cluster_id == 2  # Second highest
    assert picks[0].rank == 1
    assert picks[1].rank == 2


def test_topic_selection():
    """Test topic pick selection."""
    selector = PickSelector()
    
    clusters = [
        ClusterMetrics(1, 0.8, 0.9, 0.7, 0.6, 0.8, 0.80, 5, 2.0, 3, 2),
        ClusterMetrics(2, 0.7, 0.8, 0.6, 0.7, 0.9, 0.70, 8, 4.0, 4, 3),
        ClusterMetrics(3, 0.6, 0.7, 0.5, 0.5, 0.7, 0.60, 3, 6.0, 2, 2)
    ]
    
    topics = [
        TopicConfig(
            name="High Priority", topic_key="high_priority", queries=["test"],
            priority=2.0, max_posts_per_run=2, enabled=True
        ),
        TopicConfig(
            name="Low Priority", topic_key="low_priority", queries=["test"],
            priority=0.5, max_posts_per_run=1, enabled=True
        )
    ]
    
    cluster_topic_mapping = {
        1: "high_priority",
        2: "high_priority", 
        3: "low_priority"
    }
    
    picks = selector.select_topic_picks(clusters, topics, cluster_topic_mapping)
    
    assert len(picks) == 3  # 2 for high_priority + 1 for low_priority
    
    # Check high priority topic picks (should be first 2 by adjusted score)
    high_priority_picks = [p for p in picks if p.topic_key == "high_priority"]
    assert len(high_priority_picks) == 2
    assert high_priority_picks[0].cluster_id == 1  # 0.80 * 2.0 = 1.60
    assert high_priority_picks[1].cluster_id == 2  # 0.70 * 2.0 = 1.40
    
    # Check low priority topic pick
    low_priority_picks = [p for p in picks if p.topic_key == "low_priority"]
    assert len(low_priority_picks) == 1
    assert low_priority_picks[0].cluster_id == 3  # 0.60 * 0.5 = 0.30


def test_duplicate_removal():
    """Test duplicate removal based on centroid similarity."""
    selector = PickSelector(similarity_threshold=0.9)
    
    global_picks = [
        SelectedPick(1, 0.95, 0.95, 'global'),
        SelectedPick(2, 0.85, 0.85, 'global')
    ]
    
    topic_picks = [
        SelectedPick(3, 0.80, 1.60, 'topic', 'high_priority', 2.0),  # Very similar to cluster 1
        SelectedPick(4, 0.75, 0.75, 'topic', 'low_priority', 1.0)
    ]
    
    # Cluster 1 and 3 are very similar (should be deduplicated)
    centroids = {
        1: np.array([1.0, 0.0, 0.0, 0.0]),
        2: np.array([0.0, 1.0, 0.0, 0.0]),
        3: np.array([0.95, 0.05, 0.0, 0.0]),  # Very similar to cluster 1
        4: np.array([0.0, 0.0, 1.0, 0.0])
    }
    
    filtered_global, filtered_topic = selector.remove_duplicates(
        global_picks, topic_picks, centroids
    )
    
    # Topic pick should win over global pick due to higher priority
    assert len(filtered_global) == 1  # Cluster 2 remains
    assert len(filtered_topic) == 2  # Both topic picks remain
    assert filtered_global[0].cluster_id == 2
    assert any(p.cluster_id == 3 for p in filtered_topic)  # Cluster 3 kept (topic)
    assert any(p.cluster_id == 4 for p in filtered_topic)


def test_complete_selection():
    """Test complete selection process."""
    selector = PickSelector()
    
    clusters = [
        ClusterMetrics(1, 0.8, 0.9, 0.7, 0.6, 0.8, 0.90, 5, 2.0, 3, 2),
        ClusterMetrics(2, 0.7, 0.8, 0.6, 0.7, 0.9, 0.85, 8, 4.0, 4, 3),
        ClusterMetrics(3, 0.6, 0.7, 0.5, 0.5, 0.7, 0.80, 3, 6.0, 2, 2)
    ]
    
    sources_config = {'k_global': 10, 'max_posts_per_run': 100}
    
    topics = [
        TopicConfig(
            name="AI Topic", topic_key="ai", queries=["ai"],
            priority=1.5, max_posts_per_run=2, enabled=True
        )
    ]
    
    cluster_topic_mapping = {1: "ai", 2: "ai"}  # Cluster 3 has no topic
    
    # No centroids - no duplicate removal
    selection = selector.select_final_picks(
        clusters, sources_config, topics, cluster_topic_mapping, None
    )
    
    assert len(selection.global_picks) == 3  # All clusters selected globally
    assert len(selection.topic_picks) == 2  # 2 clusters for AI topic
    assert selection.total_picks == 5


def test_selection_dataclass():
    """Test Selection dataclass functionality."""
    global_picks = [SelectedPick(1, 0.9, 0.9, 'global')]
    topic_picks = [SelectedPick(2, 0.8, 1.2, 'topic', 'ai', 1.5)]
    
    selection = Selection(global_picks, topic_picks)
    
    assert selection.total_picks == 2
    
    data = selection.to_dict()
    assert data['total_picks'] == 2
    assert data['stats']['global_count'] == 1
    assert data['stats']['topic_count'] == 1
    assert data['stats']['topics_represented'] == 1


if __name__ == "__main__":
    # Run tests
    test_centroid_similarity()
    test_global_selection()
    test_topic_selection()
    test_duplicate_removal()
    test_complete_selection()
    test_selection_dataclass()
    print("All tests passed! ✅")