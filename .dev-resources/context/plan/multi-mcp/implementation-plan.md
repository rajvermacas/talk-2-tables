# Multi-MCP Support Implementation Plan

## Executive Summary

Implementation strategy for extending Talk 2 Tables system from single MCP server to multi-MCP architecture, enabling intelligent query routing across specialized data sources. The implementation follows a phased approach with each phase being independently executable.

## High-Level Architecture

### System Evolution
- **FROM**: Single Database MCP → FastAPI → React
- **TO**: Multiple Specialized MCPs → Orchestrator → FastAPI → React

### Key Design Decisions
1. **Static Configuration**: YAML-based MCP registry (no dynamic discovery)
2. **Priority-based Resolution**: Lower priority number = higher preference
3. **Pure LLM Approach**: No regex/rule-based matching
4. **Fail-Fast Philosophy**: Complete success or complete failure - **NO PARTIAL RESULTS EVER**
5. **No Caching**: Direct resource fetching on every request - **NO CACHING OF ANY TYPE**
6. **Comprehensive Logging**: Structured JSON for all operations
7. **SSE Transport Only**: All MCP servers use SSE transport - **NO STDIO/HTTP variations**
8. **No Health Endpoints**: Server health determined by successful tool/resource listing

## Files to Create/Modify Across All Phases

### New Files to Create
```
src/product_metadata_mcp/
├── __init__.py
├── server.py                 # Phase 1
├── metadata_store.py         # Phase 1
├── config.py                 # Phase 1
└── resources/
    └── product_metadata.json # Phase 1

fastapi_server/
├── mcp_orchestrator.py       # Phase 2
├── llm_sql_generator.py      # Phase 3
├── mcp_config.yaml           # Phase 2
└── exceptions.py             # Phase 2

tests/
├── test_product_metadata_mcp.py     # Phase 5
├── test_mcp_orchestrator.py         # Phase 5
├── test_llm_sql_generator.py        # Phase 5
├── test_multi_mcp_integration.py    # Phase 5
└── e2e_multi_mcp_test.py           # Phase 5

scripts/
├── setup_product_metadata.py        # Phase 1
├── test_multi_mcp_system.py        # Phase 5
└── validate_mcp_config.py          # Phase 2
```

### Files to Modify
```
fastapi_server/
├── main.py                   # Phase 4
├── chat_handler.py           # Phase 4
├── config.py                 # Phase 4
└── models.py                 # Phase 4

pyproject.toml                # Phase 1
.env.example                  # Phase 2
README.md                     # Phase 5
```

## Development Phases Overview

### Phase Dependencies
```
Phase 1 (Product Metadata MCP)
    ↓
Phase 2 (MCP Orchestrator)
    ↓
Phase 3 (LLM Integration)
    ↓
Phase 4 (FastAPI Integration)
    ↓
Phase 5 (Testing & Documentation)
```

### Phase Summary

| Phase | Name | Duration | Complexity | Prerequisites |
|-------|------|----------|------------|---------------|
| 1 | Product Metadata MCP Server | 2-3 hours | Medium | FastMCP understanding |
| 2 | MCP Orchestrator Component | 3-4 hours | High | Phase 1 complete |
| 3 | LLM Integration Enhancement | 2-3 hours | Medium | Phase 2 complete |
| 4 | FastAPI Integration | 2-3 hours | Medium | Phase 3 complete |
| 5 | Testing & Documentation | 3-4 hours | Low | Phase 4 complete |

## Cross-Phase Integration Points

### Data Flow Dependencies
1. **Phase 1 → Phase 2**: MCP server URL (SSE transport only)
2. **Phase 2 → Phase 3**: Direct resource collection (no caching)
3. **Phase 3 → Phase 4**: SQL generation with complete success or failure
4. **Phase 4 → Phase 5**: Complete system for end-to-end testing

### Shared Data Structures
```python
# Used across Phases 2-4
QueryResult = {
    "success": bool,
    "query": str,
    "sql": str,
    "result": {"columns": [], "rows": []},
    "error": str,
    "explanation": str,
    "resolved_entities": {},
    "metadata": {}
}

# Used in Phases 1-3
ResourceData = {
    "priority": int,
    "domains": [],
    "capabilities": [],
    "resources": {}
}
```

## Overall Testing Strategy

### Test Pyramid
```
         E2E Tests (10%)
        /            \
    Integration Tests (30%)
   /                      \
Unit Tests (60%)
```

### Test Coverage Requirements
- Unit Tests: 80% minimum coverage per component
- Integration Tests: All component interfaces
- E2E Tests: Critical user journeys

### Test Data Management
- Shared test database: `test_data/multi_mcp_test.db`
- Product metadata fixture: `test_data/product_metadata_test.json`
- Mock MCP responses: `test_data/mcp_responses/`

## Documentation Requirements

### Technical Documentation
1. **API Documentation**: OpenAPI specs for all endpoints
2. **MCP Protocol Docs**: Resource schemas and tool specifications
3. **Configuration Guide**: YAML configuration examples
4. **Troubleshooting Guide**: Common issues and solutions

### User Documentation
1. **Setup Guide**: Step-by-step installation
2. **Usage Examples**: Query patterns and capabilities
3. **Migration Guide**: Upgrading from single MCP

## Risk Mitigation

### Technical Risks
1. **MCP Connection Failures**
   - Mitigation: Fail-fast approach - if any MCP fails, entire operation fails
   - No Fallback: Complete success or complete failure only (NO PARTIAL RESULTS)

2. **LLM Hallucination**
   - Mitigation: Schema validation before SQL execution
   - Fallback: Error recovery with enhanced context

3. **Performance Degradation**
   - Mitigation: Parallel resource fetching only (NO CACHING)
   - Monitoring: Metrics for each operation stage

### Implementation Risks
1. **Phase Dependencies**
   - Mitigation: Mock interfaces for parallel development
   - Validation: Integration tests at phase boundaries

2. **Backwards Compatibility**
   - Mitigation: Feature flags for gradual rollout
   - Testing: Regression test suite

## Success Metrics

### Functional Metrics
- [ ] All 5 phases complete
- [ ] Multi-MCP queries working end-to-end
- [ ] Product resolution functioning correctly
- [ ] Error recovery implemented
- [ ] All tests passing

### Performance Metrics
- Query latency < 2 seconds (P95)
- MCP connection success rate > 99%
- LLM retry success rate > 70%
- All-or-nothing success rate (no partial results)

### Quality Metrics
- Code coverage > 80%
- Zero critical bugs
- Documentation completeness 100%
- All linting checks pass

## Rollout Strategy

### Development Environment
1. Phase 1-3: Local development
2. Phase 4: Integration testing
3. Phase 5: Full system validation

### Production Deployment
1. Feature flag: `ENABLE_MULTI_MCP=false`
2. Canary deployment: 10% traffic
3. Monitor metrics for 24 hours
4. Full rollout if metrics are green

## Maintenance Considerations

### Monitoring Points
- MCP connection health (via successful resource listing)
- Resource fetch latency (direct fetching, no cache)
- LLM response time
- SQL execution success rate
- Complete operation success rate (no partial results)

### Operational Runbooks
1. MCP server unreachable
2. LLM timeout handling
3. Cache invalidation procedures
4. Configuration updates

## Phase Execution Guide

Each phase has a dedicated implementation guide in the `phases/` directory:

1. **Phase 1**: [Product Metadata MCP Server](phases/phase-01-product-metadata-mcp.md)
2. **Phase 2**: [MCP Orchestrator Component](phases/phase-02-mcp-orchestrator.md)
3. **Phase 3**: [LLM Integration Enhancement](phases/phase-03-llm-integration.md)
4. **Phase 4**: [FastAPI Integration](phases/phase-04-fastapi-integration.md)
5. **Phase 5**: [Testing & Documentation](phases/phase-05-testing-documentation.md)

Each phase guide is completely self-contained and can be executed independently by following the instructions within.

## Quick Start for Developers

### Prerequisites Check
```bash
# Verify environment
python --version  # 3.11+
npm --version     # 8+
sqlite3 --version # 3.35+

# Clone and setup
cd /root/projects/talk-2-tables-mcp
python -m venv venv
source venv/bin/activate
pip install -e ".[dev,fastapi]"
```

### Phase Execution
```bash
# Start with Phase 1
cat .dev-resources/context/plan/multi-mcp/phases/phase-01-product-metadata-mcp.md

# Follow the implementation checklist
# Test before moving to next phase
# Update progress in phase file
```

### Validation Checkpoints
After each phase, validate:
1. All tests pass for that phase
2. No regression in existing functionality
3. Documentation updated
4. Code review checklist complete

## Conclusion

This plan provides a structured approach to implementing multi-MCP support with:
- Clear phase boundaries
- Self-contained implementation guides
- Comprehensive testing strategy
- Risk mitigation approaches
- Measurable success criteria

Total estimated time: 12-16 hours across 5 phases.