"""Trending topics processing package.

This package contains modules for:
- Topic parsing and matching (topics.py)
- Cluster scoring (score.py)  
- Clustering logic (cluster.py)
- Final pick selection (selector_final.py)
- General selection utilities (selector.py)
- Processing pipeline (pipeline.py)
- Main application (app.py)
"""

from .topics import (
    TopicConfig,
    AdvancedQueryParser,
    TopicMatcher,
    TopicClusteringManager,
    TopicsConfigParserNew,
    compile_query
)

from .score import ClusterMetrics, TrendingScorer

from .selector_final import (
    PickSelector,
    Selection,
    SelectedPick,
    run_final_selection
)

__all__ = [
    # Topics
    'TopicConfig',
    'AdvancedQueryParser', 
    'TopicMatcher',
    'TopicClusteringManager',
    'TopicsConfigParserNew',
    'compile_query',
    
    # Scoring
    'ClusterMetrics',
    'TrendingScorer',
    
    # Final selection
    'PickSelector',
    'Selection', 
    'SelectedPick',
    'run_final_selection'
]