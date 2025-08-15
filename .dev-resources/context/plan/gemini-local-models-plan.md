# Configure System for Gemini + Local Models Only

## Overview
Configure the Enhanced Intent Detection system for production deployment with:
- **Primary LLM**: Google Gemini (API-based, cost-effective)
- **Local Models**: sentence-transformers for embeddings (no API costs)
- **Remove**: OpenRouter dependency (not available in production)
- **Keep**: Semantic caching with local embeddings for performance

## ✅ User Requirements Analysis

### Current Model Usage:
1. **CLASSIFICATION_MODEL**: `meta-llama/llama-3.1-8b-instruct:free`
   - **Current**: OpenRouter API call (not available in production)
   - **Solution**: Change to Gemini model (e.g., `gemini-1.5-flash`)

2. **EMBEDDING_MODEL**: `all-MiniLM-L6-v2`
   - **Current**: Local sentence-transformers model ✅
   - **Status**: Already perfect - no API costs, runs locally

### Cost Analysis:
- **Gemini API**: Much more affordable than OpenRouter premium models
- **Local Embeddings**: Zero API costs after initial download
- **Caching Benefits**: Reduces Gemini API calls by 50-80%

## Implementation Approach

### Phase 1: Remove OpenRouter Dependencies
- [ ] Remove OpenRouter client (`openrouter_client.py`)
- [ ] Remove OpenRouter configuration fields
- [ ] Remove OpenRouter imports and references
- [ ] Update LLM manager to only support Gemini

### Phase 2: Configure Gemini as Primary Provider  
- [ ] Set default LLM provider to "gemini"
- [ ] Update default classification model to Gemini model
- [ ] Remove OpenRouter model references
- [ ] Update validation to require only Gemini API key

### Phase 3: Ensure Local Models Only for Embeddings
- [ ] Verify embedding model uses sentence-transformers (local)
- [ ] Keep semantic caching functionality (provides value with local embeddings)
- [ ] Ensure no external API calls for embeddings

### Phase 4: Update Configuration and Documentation
- [ ] Update `.env.example` with Gemini-only configuration
- [ ] Remove OpenRouter documentation
- [ ] Update architecture documentation
- [ ] Update deployment guides

## Files to be Modified

### Files to DELETE:
1. `fastapi_server/openrouter_client.py` (349 lines)

### Files to MODIFY:
1. `fastapi_server/config.py` - Remove OpenRouter fields, update defaults
2. `fastapi_server/llm_manager.py` - Remove OpenRouter provider logic
3. `fastapi_server/main.py` - Remove OpenRouter references
4. `.env.example` - Update to Gemini-only configuration
5. `tests/` - Update all tests to use Gemini config
6. Documentation files - Remove OpenRouter references

## Step-by-Step Implementation Tasks

### ✅ Step 1: Remove OpenRouter Client
- [ ] Delete `fastapi_server/openrouter_client.py`
- [ ] Remove OpenRouter imports from other files

### ✅ Step 2: Update Configuration Defaults
- [ ] Change default `llm_provider` from "openrouter" to "gemini"
- [ ] Update default `classification_model` to Gemini model
- [ ] Remove OpenRouter configuration fields
- [ ] Update validation to only support "gemini"

### ✅ Step 3: Update LLM Manager
- [ ] Remove OpenRouter provider logic from `llm_manager.py`
- [ ] Remove OpenRouter headers and initialization
- [ ] Simplify to only support Gemini provider

### ✅ Step 4: Update Main Application
- [ ] Remove OpenRouter references from `main.py`
- [ ] Update startup logs and health checks
- [ ] Update model listing to only show Gemini models

### ✅ Step 5: Update Configuration Files
- [ ] Update `.env.example` to remove OpenRouter sections
- [ ] Set Gemini as default provider
- [ ] Add Gemini API key requirements
- [ ] Remove OpenRouter API key fields

### ✅ Step 6: Update Tests
- [ ] Update all test fixtures to use Gemini configuration
- [ ] Remove OpenRouter-specific tests
- [ ] Update mock configurations for Gemini
- [ ] Ensure tests pass with Gemini-only setup

### ✅ Step 7: Update Documentation
- [ ] Update CLAUDE.md to remove OpenRouter references
- [ ] Update deployment documentation
- [ ] Update environment variable documentation
- [ ] Update session scratchpad

## Model Configuration Changes

### Before (OpenRouter):
```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct:free
CLASSIFICATION_MODEL=meta-llama/llama-3.1-8b-instruct:free
EMBEDDING_MODEL=all-MiniLM-L6-v2  # Local model ✅
```

### After (Gemini + Local):
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
CLASSIFICATION_MODEL=gemini-1.5-flash  # Gemini API
EMBEDDING_MODEL=all-MiniLM-L6-v2     # Local model ✅
```

## Testing Strategy

### Configuration Tests
- [ ] Test system starts with Gemini-only configuration
- [ ] Test validation rejects OpenRouter provider
- [ ] Test Gemini API key validation
- [ ] Test model selection with Gemini

### Integration Tests
- [ ] Test enhanced intent detection with Gemini
- [ ] Test semantic caching with local embeddings
- [ ] Test end-to-end flow: Query → Gemini → Cache → Response
- [ ] Test performance with Gemini + local embeddings

### Cost Verification
- [ ] Verify no OpenRouter API calls
- [ ] Verify embeddings are generated locally
- [ ] Verify only Gemini API calls for classification
- [ ] Test caching reduces Gemini API usage

## Benefits of This Approach

### Cost Optimization ✅
- **Gemini**: More affordable than OpenRouter premium models
- **Local Embeddings**: Zero ongoing API costs
- **Semantic Caching**: 50-80% reduction in Gemini API calls

### Performance ✅
- **Keep 3-Tier Architecture**: Fast Path → Cache → Gemini
- **Local Embeddings**: No network latency for similarity matching
- **Efficient Caching**: Maintains performance benefits

### Production Ready ✅
- **No OpenRouter Dependency**: Meets production constraints
- **Reliable API**: Google Gemini has good availability
- **Local Processing**: Embeddings don't require internet for cached queries

## Risk Assessment

### Low Risk Implementation
- **Gemini API**: Well-established, reliable Google service
- **Local Models**: sentence-transformers is mature, stable
- **Caching**: Proven to work with local embeddings
- **Configuration**: Simple provider switch

### Mitigation Strategies
- **API Limits**: Semantic caching reduces API usage
- **Offline Capability**: Local embeddings work without internet
- **Fallback**: Regex fast path handles obvious SQL queries

## Success Criteria
- [ ] System runs without OpenRouter dependencies
- [ ] Only Gemini API calls for LLM classification
- [ ] Local embedding generation works
- [ ] Semantic caching reduces API calls
- [ ] All tests pass with new configuration
- [ ] Documentation reflects Gemini-only setup

## Estimated Cost Impact
```
Current (OpenRouter): 
- Classification: OpenRouter API calls (rate limited free tier)
- Embeddings: Local (free)
- Cache hit rate: 0% (without proper setup)

After (Gemini + Local):
- Classification: Gemini API calls (~$0.00015/1K tokens)
- Embeddings: Local (free)  
- Cache hit rate: 50-80% (reduces Gemini calls)

Net Result: Much lower and predictable costs
```

## Implementation Timeline
- **Phase 1-2**: Remove OpenRouter, configure Gemini (1-2 hours)
- **Phase 3**: Verify local models (30 minutes)  
- **Phase 4**: Update documentation (1 hour)
- **Total**: 3-4 hours for complete transition