# Enhanced Intent Detection Guide

This document provides comprehensive guidance on configuring and using the Enhanced Intent Detection system in Talk-2-Tables MCP Server.

## Overview

The Enhanced Intent Detection system replaces traditional regex-based query classification with an intelligent LLM-based approach, enabling:

- **Universal Domain Support**: Works across healthcare, finance, manufacturing, retail, and other business domains without manual configuration
- **95%+ Accuracy**: Achieves high accuracy through LLM-based understanding of query context
- **Semantic Caching**: Reduces costs and improves performance through intelligent similarity-based caching
- **Future-Ready Architecture**: Designed for multi-server routing and federated query execution

## Quick Start

### 1. Enable Enhanced Detection

Update your `.env` file:

```bash
# Enable enhanced intent detection
ENABLE_ENHANCED_DETECTION=true
ROLLOUT_PERCENTAGE=1.0

# Configure semantic caching
ENABLE_SEMANTIC_CACHE=true
CACHE_BACKEND=memory
```

### 2. Install Dependencies

```bash
pip install -e ".[dev,fastapi]"
```

The system will automatically install the required dependencies:
- `redis>=4.5.0` (for distributed caching)
- `sentence-transformers>=2.2.0` (for semantic similarity)
- `numpy>=1.24.0` (for similarity calculations)
- `scikit-learn>=1.3.0` (for machine learning utilities)

### 3. Start the System

```bash
# Start MCP server
python -m talk_2_tables_mcp.remote_server

# Start FastAPI server with enhanced detection
cd fastapi_server && python main.py
```

## Configuration Options

### Enhanced Intent Detection

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ENABLE_ENHANCED_DETECTION` | `false` | Enable LLM-based intent detection |
| `ENABLE_HYBRID_MODE` | `false` | Run both legacy and enhanced for comparison |
| `ROLLOUT_PERCENTAGE` | `0.0` | Percentage of queries using enhanced detection (0.0-1.0) |

### LLM Classification Settings

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `CLASSIFICATION_MODEL` | `meta-llama/llama-3.1-8b-instruct:free` | LLM model for intent classification |
| `CLASSIFICATION_TEMPERATURE` | `0.0` | Temperature for deterministic classification |
| `CLASSIFICATION_MAX_TOKENS` | `10` | Maximum tokens for classification response |
| `CLASSIFICATION_TIMEOUT_SECONDS` | `30` | Timeout for classification requests |

### Semantic Caching Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ENABLE_SEMANTIC_CACHE` | `true` | Enable semantic similarity caching |
| `CACHE_BACKEND` | `memory` | Cache backend: `memory` or `redis` |
| `CACHE_TTL_SECONDS` | `3600` | Cache time-to-live (1 hour) |
| `MAX_CACHE_SIZE` | `10000` | Maximum cache entries |
| `SIMILARITY_THRESHOLD` | `0.85` | Minimum similarity for cache match |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence transformer model |

### Redis Configuration (Optional)

For production deployments with multiple server instances:

```bash
# Redis configuration
CACHE_BACKEND=redis
REDIS_URL=redis://localhost:6379/0
```

### Performance Optimization

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ENABLE_BACKGROUND_CACHING` | `true` | Enable background cache warming |
| `CACHE_WARMUP_ON_STARTUP` | `true` | Warm cache on system startup |
| `MAX_CONCURRENT_CLASSIFICATIONS` | `10` | Max concurrent LLM calls |

### Monitoring and Alerts

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ENABLE_DETECTION_METRICS` | `true` | Enable metrics collection |
| `LOG_CLASSIFICATIONS` | `true` | Log classification decisions |
| `ACCURACY_ALERT_THRESHOLD` | `0.85` | Alert if accuracy drops below 85% |
| `CACHE_HIT_RATE_ALERT_THRESHOLD` | `0.40` | Alert if cache hit rate drops below 40% |

## Deployment Strategies

### Development Mode

For testing and development:

```bash
ENABLE_ENHANCED_DETECTION=true
ENABLE_HYBRID_MODE=true
ROLLOUT_PERCENTAGE=0.5
CACHE_BACKEND=memory
LOG_CLASSIFICATIONS=true
```

### Gradual Production Rollout

Phase 1 - Initial deployment (10% of users):
```bash
ENABLE_ENHANCED_DETECTION=true
ROLLOUT_PERCENTAGE=0.1
ENABLE_COMPARISON_LOGGING=true
```

Phase 2 - Expanded rollout (50% of users):
```bash
ROLLOUT_PERCENTAGE=0.5
```

Phase 3 - Full rollout (100% of users):
```bash
ROLLOUT_PERCENTAGE=1.0
ENABLE_COMPARISON_LOGGING=false
```

### Production Configuration

For high-availability production deployments:

```bash
# Enhanced detection
ENABLE_ENHANCED_DETECTION=true
ROLLOUT_PERCENTAGE=1.0
ENABLE_HYBRID_MODE=false

# Redis caching for multiple instances
CACHE_BACKEND=redis
REDIS_URL=redis://redis-cluster:6379/0
CACHE_TTL_SECONDS=7200
MAX_CACHE_SIZE=50000

# Performance optimization
ENABLE_BACKGROUND_CACHING=true
MAX_CONCURRENT_CLASSIFICATIONS=20

# Monitoring
ENABLE_DETECTION_METRICS=true
ACCURACY_ALERT_THRESHOLD=0.90
CACHE_HIT_RATE_ALERT_THRESHOLD=0.60
```

## Multi-Domain Usage

The enhanced system automatically adapts to different business domains:

### Healthcare
```json
{
  "query": "Show me patient readmission rates by department",
  "business_domain": "healthcare"
}
```

### Finance
```json
{
  "query": "What's our portfolio variance across sectors?",
  "business_domain": "finance"
}
```

### Manufacturing
```json
{
  "query": "What's our line efficiency for Q2?",
  "business_domain": "manufacturing"
}
```

### Retail
```json
{
  "query": "Show me sales data for last quarter",
  "business_domain": "retail"
}
```

## Performance Monitoring

### Access Detection Statistics

```python
from fastapi_server.chat_handler import chat_handler

# Get comprehensive statistics
stats = chat_handler.get_detection_stats()

print(f"Cache hit rate: {stats['cache_stats']['hit_rate']:.1%}")
print(f"Average response time: {stats['detection_metrics']['avg_classification_time_ms']:.1f}ms")
print(f"Total classifications: {stats['detection_metrics']['total_classifications']}")
```

### Cache Management

```python
# Warm cache for specific domain
result = await chat_handler.warm_cache_for_domain("healthcare")
print(f"Cached {result['patterns_cached']} patterns")

# Assess domain complexity
assessment = await chat_handler.assess_domain_complexity(
    "finance", 
    ["What's our portfolio performance?", "Show me risk metrics"]
)
print(f"Domain risk level: {assessment['assessment']['risk_level']}")
```

## Testing

### Multi-Domain Validation

Run comprehensive testing across business domains:

```bash
python scripts/test_multi_domain_queries.py
```

This validates accuracy across:
- Healthcare queries
- Financial analysis requests
- Manufacturing operations
- Retail analytics
- Legal case management
- Educational administration

### Unit Testing

Run the enhanced detection test suite:

```bash
# Test enhanced intent detector
pytest tests/test_enhanced_intent_detector.py -v

# Test semantic caching
pytest tests/test_semantic_cache.py -v

# Run all tests
pytest tests/ -v
```

## Troubleshooting

### Common Issues

1. **Low Cache Hit Rate**
   - Check `SIMILARITY_THRESHOLD` (try lowering to 0.80)
   - Ensure `ENABLE_SEMANTIC_CACHE=true`
   - Verify embedding model is loading correctly

2. **High Response Times**
   - Enable background caching: `ENABLE_BACKGROUND_CACHING=true`
   - Use faster classification model
   - Increase `MAX_CONCURRENT_CLASSIFICATIONS`

3. **Poor Classification Accuracy**
   - Check if database metadata is properly configured
   - Verify LLM model is accessible
   - Consider domain-specific cache warming

### Debug Logging

Enable detailed logging for troubleshooting:

```bash
LOG_LEVEL=DEBUG
LOG_CLASSIFICATIONS=true
ENABLE_COMPARISON_LOGGING=true
```

### Health Checks

Monitor system health:

```bash
curl http://localhost:8001/health
```

## Migration from Legacy System

### Step 1: Parallel Testing

```bash
ENABLE_ENHANCED_DETECTION=true
ENABLE_HYBRID_MODE=true
ROLLOUT_PERCENTAGE=0.0  # Still using legacy
ENABLE_COMPARISON_LOGGING=true
```

### Step 2: Gradual Rollout

```bash
ROLLOUT_PERCENTAGE=0.1  # 10% enhanced, 90% legacy
```

### Step 3: Validation

Monitor metrics and gradually increase:

```bash
ROLLOUT_PERCENTAGE=0.25  # 25% enhanced
ROLLOUT_PERCENTAGE=0.50  # 50% enhanced
ROLLOUT_PERCENTAGE=1.0   # 100% enhanced
```

### Step 4: Legacy Removal

```bash
ENABLE_HYBRID_MODE=false
ENABLE_COMPARISON_LOGGING=false
```

## Cost Optimization

### Estimated Costs

With proper caching (60% hit rate):
- **Development**: ~$0.50/day (1000 queries)
- **Production**: ~$5-20/day (10k-50k queries)

### Cost Reduction Strategies

1. **Optimize Cache Hit Rate**
   - Use domain-specific cache warming
   - Tune similarity threshold
   - Enable embedding caching

2. **Model Selection**
   - Use free models for development
   - Consider local models for privacy-sensitive deployments

3. **Request Batching**
   - Configure `MAX_CONCURRENT_CLASSIFICATIONS` appropriately
   - Use background caching during off-peak hours

## Support and Resources

- **Architecture Document**: `.dev-resources/architecture/enhanced-intent-detection-architecture.md`
- **Test Scripts**: `scripts/test_multi_domain_queries.py`
- **Configuration Reference**: `.env.example`
- **API Documentation**: Built-in FastAPI docs at `/docs`