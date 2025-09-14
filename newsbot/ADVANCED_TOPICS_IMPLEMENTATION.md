# Advanced Topic Parsing & Clustering System

## Overview

This implementation provides a sophisticated topic-based content analysis system with advanced query parsing capabilities, domain/language filtering, cadence control, and topic-separated clustering for the NewsBot project.

## ✅ Features Implemented

### 🔍 Advanced Query Parser (`AdvancedQueryParser`)

**Phrase Matching with Quotes:**
```python
'"machine learning"'  # Exact phrase match
'"artificial intelligence"'  # Case-insensitive exact match
```

**Boolean Operators:**
```python
'AI AND machine'          # Both terms must be present
'neural OR quantum'       # Either term must be present  
'deep AND learning OR ai' # Complex boolean expressions
```

**Proximity Operators (NEAR/n):**
```python
'neural NEAR/3 networks'   # "neural" within 3 tokens of "networks"
'machine NEAR/5 learning'  # "machine" within 5 tokens of "learning"
```

**Complex Combined Queries:**
```python
'"machine learning" AND neural'                    # Phrase + Boolean
'artificial AND neural NEAR/3 networks'           # Boolean + Proximity
'"artificial intelligence" OR ai NEAR/2 systems'  # Multi-operator
```

### 🎯 Topic Configuration (`TopicConfig`)

**Comprehensive Topic Settings:**
```python
TopicConfig(
    name="AI Technology",
    topic_key="ai_tech",                    # Unique identifier
    queries=[                               # Advanced query list
        '"machine learning"',
        'AI AND neural', 
        'artificial NEAR/2 intelligence'
    ],
    allow_domains=['tech.com', 'ai.org'],   # Domain whitelist
    lang='en',                              # Language filter
    cadence_minutes=30,                     # Run frequency
    max_posts_per_run=20,                   # Rate limiting
    boost_factor=1.2,                       # Score multiplier
    min_score=0.1,                          # Quality threshold
    enabled=True                            # Enable/disable
)
```

### 🔗 Topic Matcher (`TopicMatcher`)

**Multi-Layer Filtering:**
1. **Domain Filtering**: Whitelist specific domains
2. **Language Filtering**: Filter by content language  
3. **Advanced Query Matching**: Use sophisticated parser
4. **Score Calculation**: Weighted relevance scoring
5. **Rate Limiting**: Respect `max_posts_per_run`

**Text Normalization:**
- Combines `title + " " + summary` for matching
- Handles missing fields gracefully
- Case-insensitive matching

### ⏰ Cadence Control (`TopicClusteringManager`)

**Time-Based Processing:**
- Each topic has independent cadence control
- Prevents over-processing of high-frequency topics
- Configurable per-topic timing (minutes)
- Persistent timing across service restarts

**Topic-Separated Clustering:**
- Each topic maintains separate clusters via `topic_key`
- Prevents cross-contamination between topics
- Independent scoring and ranking per topic

### 📊 Scoring Integration

**Seamless Integration with Existing Scoring System:**
- Uses the implemented `score_and_rank_clusters()` function
- Topic-filtered cluster ranking via `topic_key` parameter
- Maintains all scoring metrics (trend, diversity, freshness)
- Returns top-K clusters per topic

### 🗂️ Configuration Management (`TopicsConfigParserNew`)

**YAML/Dictionary Loading:**
```yaml
topics:
  - name: "AI & Machine Learning"
    topic_key: "ai_ml"
    queries:
      - '"artificial intelligence"'
      - 'machine AND learning'
      - 'neural NEAR/3 network'
    allow_domains: ['tech.com', 'ai.org']
    lang: 'en'
    cadence_minutes: 30
    max_posts_per_run: 10
    boost_factor: 1.5
    min_score: 0.3
    enabled: true
```

### 🚀 Pipeline Integration (`analyze_topic_trends_advanced`)

**Complete Processing Pipeline:**
1. **Multi-Topic Processing**: Handle multiple topics simultaneously
2. **Cadence Respect**: Skip topics that haven't reached cadence
3. **Item Filtering**: Apply all filters (domain, language, queries)
4. **Clustering**: Topic-separated clustering with `topic_key`
5. **Scoring & Ranking**: Top-K clusters per topic
6. **Error Handling**: Graceful error recovery per topic
7. **Comprehensive Reporting**: Detailed results and metrics

## 🧪 Testing Coverage

**Comprehensive Test Suite (20 tests, all passing):**

- **AdvancedQueryParser (7 tests)**: Phrase extraction, NEAR operations, boolean expressions, complex combinations
- **TopicConfig (2 tests)**: Default values, dictionary loading
- **TopicMatcher (4 tests)**: Domain filtering, language filtering, scoring, complete filtering
- **TopicClusteringManager (3 tests)**: Cadence control, disabled topics, item processing  
- **TopicsConfigParser (2 tests)**: Dictionary loading, empty configs
- **Pipeline Integration (2 tests)**: Complete analysis, cadence control

## 📋 Usage Examples

### Basic Topic Definition
```python
topic = TopicConfig(
    name="Climate Change",
    topic_key="climate",
    queries=['"climate change"', 'global AND warming'],
    allow_domains=['climate.org'],
    lang='en'
)
```

### Advanced Query Patterns
```python
queries = [
    '"artificial intelligence"',           # Exact phrase
    'machine AND learning',                # Both required
    'AI OR "machine learning"',            # Either phrase or term
    'neural NEAR/3 networks',              # Proximity search
    '"deep learning" AND computer',        # Phrase + boolean
    'data NEAR/2 science OR analytics'     # Complex combination
]
```

### Pipeline Execution
```python
results = await analyze_topic_trends_advanced(
    items=news_items,
    topics_config=topics_list,
    session=db_session,
    clusterer=incremental_clusterer,
    max_clusters_per_topic=10
)

# Results structure:
{
    'summary': {
        'total_topics': 3,
        'topics_processed': 2, 
        'total_items_matched': 15,
        'total_clusters_updated': 8
    },
    'topics': {
        'ai_tech': {
            'processed': True,
            'items_matched': 8,
            'top_clusters': [...],
            'clusters_updated': [1, 2, 3]
        }
    }
}
```

## 🔧 Technical Implementation Details

### Query Parser Architecture
- **Placeholder Strategy**: Replaces complex patterns with placeholders during parsing
- **Multi-Pass Processing**: Handles phrases, NEAR ops, then boolean expressions
- **Robust Boolean Evaluation**: Supports nested AND/OR with proper precedence
- **Error Recovery**: Graceful handling of malformed queries

### Performance Optimizations
- **Early Exit**: Short-circuit evaluation on failed phrase/NEAR matches
- **Compiled Regex**: Pre-compiled patterns for efficient matching
- **Minimal Text Processing**: Optimized text normalization
- **Batch Processing**: Efficient handling of multiple topics

### Integration Points
- **Existing Scoring System**: Seamless integration with `score_and_rank_clusters`
- **Database Models**: Compatible with existing cluster/item models
- **Caching Layer**: Works with existing Redis caching infrastructure
- **Configuration System**: Integrates with existing Pydantic settings

## 🚀 Demonstration

Run the comprehensive demo:
```bash
cd "c:\WWW\Wind World Wire\newsbot"
uv run python demo_topics.py
```

Run the test suite:
```bash
uv run python -m pytest tests/test_topics_advanced.py -v
```

## 📈 Performance Metrics

**Test Results:**
- ✅ 20/20 tests passing
- ✅ All query patterns working correctly
- ✅ Domain/language filtering functional
- ✅ Cadence control operational  
- ✅ Topic-separated clustering verified
- ✅ Pipeline integration complete
- ✅ Error handling robust

**Query Parser Capabilities:**
- ✅ Phrase matching: `"exact phrase"`
- ✅ Boolean operators: `AND`, `OR`  
- ✅ Proximity operators: `NEAR/n`
- ✅ Complex combinations: `"phrase" AND term NEAR/3 other`
- ✅ Case-insensitive matching
- ✅ Multi-language support

This implementation provides a production-ready, highly sophisticated topic analysis system that extends the existing NewsBot architecture with advanced query capabilities while maintaining full backward compatibility.