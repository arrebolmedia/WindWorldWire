# Trending System Parameters Configuration

This document describes all the recommended parameters for the NewsBot trending topics system, optimized for production use.

## Environment Variables (.env)

### Core Trending Parameters

```bash
# Similarity threshold for clustering (0.0-1.0, higher = more similar required)
TREND_SIM_THRESHOLD=0.78
```
**Description**: Controls how similar articles need to be to cluster together. Higher values (0.7-0.9) create tighter, more focused clusters. Lower values (0.5-0.7) create broader clusters.
**Recommended**: 0.78 for balanced clustering that groups related articles without over-merging different topics.

```bash
# Default number of nearest neighbors for clustering
TREND_NEAR_DEFAULT=3
```
**Description**: Number of nearest neighbors to consider when forming clusters. Affects cluster size and coherence.
**Recommended**: 3 provides good balance between cluster quality and computational efficiency.

```bash
# Global selection limit for trending items per run
SELECTION_K_GLOBAL=3
```
**Description**: Maximum number of trending items to select globally across all topics per analysis run.
**Recommended**: 3 ensures focused, high-quality trending content without overwhelming users.

```bash
# Freshness decay time constant in hours (affects recency scoring)
FRESHNESS_TAU_HOURS=3
```
**Description**: Time constant for exponential decay of freshness scores. Articles older than this value start losing freshness rapidly.
**Recommended**: 3 hours prioritizes very recent content while still considering slightly older articles.

### Feature Flags

```bash
# Enable trending detection system
FEATURE_TREND_DETECTION=true
```

## Sources Configuration (sources.yaml)

### Processing Limits

```yaml
# Maximum posts to process per run (global default)
max_posts_per_run: 100

# Maximum posts per source per run (prevents any single source from dominating)
max_posts_per_source: 20

# Trending system: Maximum posts to analyze for trending per run
max_trending_posts_per_run: 50
```

**Recommendations**:
- `max_posts_per_run: 100` - Balances comprehensive coverage with processing time
- `max_posts_per_source: 20` - Prevents single sources from overwhelming trending analysis
- `max_trending_posts_per_run: 50` - Focused subset for trending analysis efficiency

## Topics Configuration (topics.yaml)

### Required Fields for All Topics

Every topic should include these parameters:

```yaml
- name: "Topic Name"
  slug: "topic-slug"
  description: "Topic description"
  priority: 0.8              # 0.0-1.0, higher = more important
  cadence: hourly
  cadence_minutes: 120       # How often to check for trending content
  max_posts_per_run: 3       # Max trending items per topic per run
  lang: [es, en]             # Supported languages
  allow_domains: []          # Empty = all domains, or specify allowed domains
  keywords: [...]            # Topic keywords
  parent: null               # Parent topic (if any)
```

### Priority Guidelines

**Priority Ranges** (0.0-1.0):
- **0.9-1.0**: Critical topics (breaking news, major economic policy, high-impact security)
- **0.7-0.9**: High priority (technology, financial markets, major business news)
- **0.5-0.7**: Medium priority (industry sectors, regional news)
- **0.3-0.5**: Lower priority (lifestyle, opinion, niche topics)
- **0.0-0.3**: Background monitoring (very specialized content)

### Cadence Guidelines

**cadence_minutes** recommendations by topic type:
- **30-60 minutes**: Breaking news, security, critical economic topics
- **120-180 minutes**: Business news, technology, financial markets
- **240-360 minutes**: Industry sectors, policy updates
- **480-720 minutes**: Analysis, opinion, specialized content

### max_posts_per_run Guidelines

**Recommended values** by topic importance:
- **5-6 posts**: Very high priority topics (major news categories)
- **3-4 posts**: High priority topics (important business sectors)
- **2-3 posts**: Medium priority topics (specialized sectors)
- **1-2 posts**: Lower priority topics (niche content, opinion)

### Domain Restrictions

**allow_domains** strategy:
- **Empty array `[]`**: Allow all domains (recommended for most topics)
- **Specific domains**: Restrict to trusted sources for sensitive topics
- **Examples**:
  - Financial topics: `["bloomberg.com", "reuters.com", "wsj.com", "ft.com"]`
  - Technology: `["techcrunch.com", "wired.com", "bloomberg.com", "reuters.com"]`
  - General news: `["reuters.com", "apnews.com", "bbc.com"]`

## Example Topic Configurations

### High Priority Topic (Security/Policy)
```yaml
- key: taiwan_seguridad
  name: "Taiwán y seguridad regional"
  priority: 0.9
  cadence: hourly
  cadence_minutes: 30        # Check every 30 minutes
  max_posts_per_run: 3
  lang: [es, en]
  allow_domains: ["reuters.com","apnews.com","bbc.com","aljazeera.com"]
  queries:
    - '"Taiwan" OR "Taipei" OR "Taipéi"'
  tags: ["Asia","Defensa","China","Taiwán"]
```

### Medium Priority Topic (Business Sector)
```yaml
- name: "Tecnología y Fintech"
  slug: "tecnologia-fintech"
  priority: 0.8
  cadence: hourly
  cadence_minutes: 90        # Check every 1.5 hours
  max_posts_per_run: 6
  lang: [es, en]
  allow_domains: ["techcrunch.com", "wired.com", "bloomberg.com", "reuters.com"]
  keywords: ["fintech", "blockchain", "inteligencia artificial"]
```

### Lower Priority Topic (Opinion/Analysis)
```yaml
- name: "Análisis y Opinión"
  slug: "analisis-opinion"
  priority: 0.3
  cadence: hourly
  cadence_minutes: 480       # Check every 8 hours
  max_posts_per_run: 2
  lang: [es, en]
  allow_domains: []          # Allow all domains
  keywords: ["análisis", "opinión", "columna"]
```

## Performance Considerations

### Memory and CPU Usage
- **TREND_SIM_THRESHOLD**: Higher values reduce computation but may miss related content
- **TREND_NEAR_DEFAULT**: Higher values increase accuracy but require more computation
- **max_posts_per_run**: Higher values provide better coverage but increase processing time

### Database Impact
- **cadence_minutes**: More frequent checks increase database load
- **max_posts_per_run**: Higher values increase database queries and storage

### Content Quality
- **SELECTION_K_GLOBAL**: Lower values focus on highest quality but may miss important stories
- **priority**: Properly set priorities ensure important topics get adequate coverage
- **allow_domains**: Domain restrictions improve quality but may limit coverage

## Monitoring and Tuning

### Key Metrics to Monitor
1. **Cluster Quality**: Are related articles clustering together?
2. **Coverage**: Are important stories being detected?
3. **Freshness**: Are trending items sufficiently recent?
4. **Diversity**: Are trending items covering different topics appropriately?
5. **Performance**: Processing time per run, memory usage

### Tuning Guidelines
1. **Start Conservative**: Begin with suggested values
2. **Monitor Results**: Track trending quality over 1-2 weeks
3. **Adjust Gradually**: Change one parameter at a time
4. **A/B Test**: Compare different parameter sets if possible
5. **Seasonal Adjustment**: Consider adjusting for news cycles and events

## Production Deployment Checklist

- [ ] Set all environment variables in `.env`
- [ ] Configure all topics with required parameters
- [ ] Set appropriate priority levels for all topics
- [ ] Configure cadence based on topic importance
- [ ] Set domain restrictions for sensitive topics
- [ ] Test with small max_posts_per_run values initially
- [ ] Monitor performance and adjust as needed
- [ ] Document any custom parameter changes