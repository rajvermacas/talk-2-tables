# Phase 3: LLM Integration Enhancement

## Phase Overview

### Objective
Enhance the LLM integration to generate SQL queries using comprehensive metadata from multiple MCP servers, including entity resolution, query translation, and intelligent error recovery.

### Scope
- Build comprehensive prompt generation with all MCP resources
- Implement entity resolution using metadata
- Create SQL generation with product aliases and column mappings
- Develop LLM response parsing and validation
- Add SQL failure recovery mechanism
- Integrate with existing LLM infrastructure

### Prerequisites
- Phase 1 complete (Product Metadata MCP running)
- Phase 2 complete (MCP Orchestrator functional)
- Existing LLM client (OpenRouter/Gemini)
- Understanding of prompt engineering
- SQL query knowledge

### Success Criteria
- [ ] LLM generates correct SQL using fresh metadata (no cache)
- [ ] Entity resolution works for product aliases
- [ ] Column mappings translate correctly
- [ ] SQL validation catches common errors
- [ ] Error recovery succeeds in 70%+ cases (or fails completely)
- [ ] Response includes explanations
- [ ] Fail-fast on any MCP unavailability

## Architectural Guidance

### Design Pattern
**Template Method Pattern**: Structured prompt generation with variable context injection
- Base prompt template with placeholders
- Context injection from MCP resources
- Response parsing with fallbacks
- Validation pipeline for generated SQL

### Code Structure
```
fastapi_server/
├── llm_sql_generator.py    # Main SQL generation logic
├── prompt_templates.py      # Prompt templates and builders
├── sql_validator.py         # SQL validation utilities
└── recovery_handler.py      # SQL error recovery logic
```

### Data Models

#### LLM Request Structure
```python
@dataclass
class LLMSQLRequest:
    user_query: str
    all_resources: Dict[str, Any]  # From orchestrator
    context: Dict[str, Any]        # Additional context
    attempt_number: int = 1
    previous_error: Optional[str] = None
```

#### LLM Response Structure
```python
@dataclass
class LLMSQLResponse:
    sql_query: str
    resolved_entities: Dict[str, Dict[str, str]]
    explanation: str
    confidence: float  # 0.0 to 1.0
    metadata: Dict[str, Any]
```

#### SQL Validation Result
```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    referenced_tables: List[str]
    referenced_columns: List[str]
```

### Technology Stack
- **LLM Client**: Existing OpenRouter/Gemini integration
- **SQL Parsing**: sqlparse for validation
- **JSON Parsing**: Built-in json with fallbacks
- **Template Engine**: String templates or Jinja2
- **Validation**: Custom SQL validator

## Detailed Implementation Tasks

### Task 1: Prompt Template System (`prompt_templates.py`)
- [ ] Create base prompt template:
  ```python
  BASE_PROMPT_TEMPLATE = """
  You are a SQL query generator with access to multiple data sources.
  
  USER QUERY: {user_query}
  
  AVAILABLE RESOURCES (sorted by priority):
  {resources_section}
  
  PRODUCT METADATA:
  {product_metadata_section}
  
  COLUMN MAPPINGS:
  {column_mappings_section}
  
  DATABASE SCHEMA:
  {database_schema_section}
  
  INSTRUCTIONS:
  1. Resolve any product names using the metadata
  2. Translate user-friendly terms using column mappings
  3. Generate a valid SQL SELECT query
  4. Include explanations for any resolutions
  
  RESPONSE FORMAT:
  {{
      "sql_query": "SELECT ...",
      "resolved_entities": {{
          "products": {{"user_term": "resolved_value"}},
          "columns": {{"friendly_name": "sql_column"}}
      }},
      "explanation": "Explanation of query generation",
      "confidence": 0.95
  }}
  """
  ```
- [ ] Build section formatters for each resource type
- [ ] Add error recovery prompt template
- [ ] Create validation prompt template

### Task 2: Main SQL Generator (`llm_sql_generator.py`)
- [ ] Implement generator class:
  ```python
  class LLMSQLGenerator:
      def __init__(self, llm_client):
          self.llm_client = llm_client
          self.validator = SQLValidator()
          self.recovery_handler = RecoveryHandler()
          
      async def generate_sql(
          self,
          user_query: str,
          all_resources: Dict[str, Any],
          context: Dict[str, Any] = None
      ) -> LLMSQLResponse:
          """Generate SQL using LLM with all metadata context"""
          
          # Build comprehensive prompt (resources fetched fresh from orchestrator)
          prompt = self._build_prompt(user_query, all_resources, context)
          
          # Send to LLM
          llm_response = await self.llm_client.generate(prompt)
          
          # Parse response
          parsed_response = self._parse_llm_response(llm_response)
          
          # Validate SQL
          validation_result = self.validator.validate(
              parsed_response.sql_query,
              all_resources
          )
          
          if not validation_result.is_valid:
              # Attempt recovery
              return await self._handle_validation_failure(
                  user_query,
                  parsed_response,
                  validation_result,
                  all_resources
              )
              
          return parsed_response
  ```
- [ ] Implement prompt building logic
- [ ] Add response parsing with fallbacks
- [ ] Handle multiple LLM response formats

### Task 3: Prompt Building Algorithm
- [ ] Create comprehensive prompt builder:
  ```python
  def _build_prompt(
      self,
      user_query: str,
      all_resources: Dict[str, Any],
      context: Dict[str, Any] = None,
      is_recovery: bool = False,
      previous_error: str = None
  ) -> str:
      """Build prompt with all available context"""
      
      # Sort resources by priority
      sorted_resources = sorted(
          all_resources.items(),
          key=lambda x: x[1].get('priority', 999)
      )
      
      # Format resources section
      resources_lines = []
      for server_name, server_data in sorted_resources:
          resources_lines.append(
              f"Server: {server_name} (Priority: {server_data['priority']})"
          )
          resources_lines.append(f"Domains: {', '.join(server_data['domains'])}")
          resources_lines.append(f"Capabilities: {', '.join(server_data['capabilities'])}")
          resources_lines.append("---")
      
      # Extract product metadata
      product_metadata = self._extract_product_metadata(all_resources)
      
      # Extract column mappings
      column_mappings = self._extract_column_mappings(all_resources)
      
      # Extract database schema
      database_schema = self._extract_database_schema(all_resources)
      
      # Build final prompt
      if is_recovery:
          template = ERROR_RECOVERY_TEMPLATE
          return template.format(
              user_query=user_query,
              previous_sql=context.get('previous_sql'),
              error_message=previous_error,
              resources_section='\n'.join(resources_lines),
              product_metadata_section=json.dumps(product_metadata, indent=2),
              column_mappings_section=json.dumps(column_mappings, indent=2),
              database_schema_section=json.dumps(database_schema, indent=2)
          )
      else:
          return BASE_PROMPT_TEMPLATE.format(
              user_query=user_query,
              resources_section='\n'.join(resources_lines),
              product_metadata_section=json.dumps(product_metadata, indent=2),
              column_mappings_section=json.dumps(column_mappings, indent=2),
              database_schema_section=json.dumps(database_schema, indent=2)
          )
  ```
- [ ] Add metadata extraction helpers
- [ ] Format schema information clearly
- [ ] Include examples in prompt

### Task 4: Response Parsing (`_parse_llm_response`)
- [ ] Implement robust parser:
  ```python
  def _parse_llm_response(self, llm_text: str) -> LLMSQLResponse:
      """Parse LLM response with multiple fallback strategies"""
      
      # Strategy 1: Try direct JSON parsing
      try:
          # Extract JSON from response
          json_match = re.search(r'\{.*\}', llm_text, re.DOTALL)
          if json_match:
              data = json.loads(json_match.group())
              return LLMSQLResponse(
                  sql_query=data['sql_query'],
                  resolved_entities=data.get('resolved_entities', {}),
                  explanation=data.get('explanation', ''),
                  confidence=data.get('confidence', 0.8),
                  metadata=data.get('metadata', {})
              )
      except (json.JSONDecodeError, KeyError):
          pass
      
      # Strategy 2: Extract SQL using patterns
      sql_patterns = [
          r'SELECT\s+.*?\s+FROM\s+.*?(?:;|$)',
          r'```sql\n(.*?)\n```',
          r'SQL:\s*(SELECT.*?)(?:\n|$)'
      ]
      
      for pattern in sql_patterns:
          match = re.search(pattern, llm_text, re.IGNORECASE | re.DOTALL)
          if match:
              sql_query = match.group(1) if '(' in pattern else match.group()
              return LLMSQLResponse(
                  sql_query=sql_query.strip(),
                  resolved_entities={},
                  explanation=self._extract_explanation(llm_text),
                  confidence=0.6,
                  metadata={'parsing_strategy': 'pattern_matching'}
              )
      
      # Strategy 3: Last resort - assume entire response is SQL
      lines = llm_text.strip().split('\n')
      for line in lines:
          if 'SELECT' in line.upper():
              return LLMSQLResponse(
                  sql_query=line,
                  resolved_entities={},
                  explanation='',
                  confidence=0.3,
                  metadata={'parsing_strategy': 'fallback'}
              )
      
      raise ValueError(f"Could not parse SQL from LLM response: {llm_text[:200]}")
  ```
- [ ] Add explanation extraction
- [ ] Handle markdown code blocks
- [ ] Parse entity resolutions

### Task 5: SQL Validator (`sql_validator.py`)
- [ ] Create validation class:
  ```python
  class SQLValidator:
      def __init__(self):
          self.dangerous_keywords = [
              'INSERT', 'UPDATE', 'DELETE', 'DROP', 
              'CREATE', 'ALTER', 'TRUNCATE'
          ]
          
      def validate(
          self,
          sql_query: str,
          all_resources: Dict[str, Any]
      ) -> ValidationResult:
          """Validate SQL against schema and security rules"""
          
          errors = []
          warnings = []
          
          # Security check
          for keyword in self.dangerous_keywords:
              if keyword in sql_query.upper():
                  errors.append(f"Dangerous keyword '{keyword}' not allowed")
          
          # Parse SQL
          try:
              parsed = sqlparse.parse(sql_query)[0]
          except Exception as e:
              errors.append(f"SQL syntax error: {e}")
              return ValidationResult(
                  is_valid=False,
                  errors=errors,
                  warnings=warnings,
                  referenced_tables=[],
                  referenced_columns=[]
              )
          
          # Extract references
          tables = self._extract_tables(parsed)
          columns = self._extract_columns(parsed)
          
          # Validate against schema
          schema = self._get_database_schema(all_resources)
          
          for table in tables:
              if table not in schema:
                  errors.append(f"Table '{table}' not found in schema")
          
          for column in columns:
              # Check if column exists in any referenced table
              if not self._column_exists(column, tables, schema):
                  warnings.append(f"Column '{column}' may not exist")
          
          return ValidationResult(
              is_valid=len(errors) == 0,
              errors=errors,
              warnings=warnings,
              referenced_tables=tables,
              referenced_columns=columns
          )
  ```
- [ ] Implement table extraction from SQL
- [ ] Add column extraction logic
- [ ] Validate against actual schema

### Task 6: Error Recovery Handler (`recovery_handler.py`)
- [ ] Implement recovery logic:
  ```python
  class RecoveryHandler:
      MAX_RETRY_ATTEMPTS = 3
      
      async def handle_sql_failure(
          self,
          failed_sql: str,
          error_message: str,
          user_query: str,
          all_resources: Dict[str, Any],
          llm_client: Any,
          attempt_number: int = 1
      ) -> Optional[LLMSQLResponse]:
          """Attempt to recover from SQL execution failure"""
          
          if attempt_number > self.MAX_RETRY_ATTEMPTS:
              return None
          
          # Categorize error
          error_type = self._categorize_error(error_message)
          
          if error_type == 'PERMISSION_ERROR':
              return None  # Cannot recover
          
          # Build recovery prompt
          recovery_prompt = self._build_recovery_prompt(
              user_query=user_query,
              failed_sql=failed_sql,
              error_message=error_message,
              error_type=error_type,
              all_resources=all_resources
          )
          
          # Request correction from LLM
          llm_response = await llm_client.generate(recovery_prompt)
          
          # Parse corrected SQL
          corrected_response = self._parse_correction(llm_response)
          
          # Validate before returning
          validator = SQLValidator()
          validation = validator.validate(
              corrected_response.sql_query,
              all_resources
          )
          
          if validation.is_valid:
              corrected_response.metadata['recovery_attempt'] = attempt_number
              corrected_response.metadata['original_error'] = error_type
              return corrected_response
          
          # Recursive retry
          return await self.handle_sql_failure(
              corrected_response.sql_query,
              str(validation.errors),
              user_query,
              all_resources,
              llm_client,
              attempt_number + 1
          )
  ```
- [ ] Add error categorization logic
- [ ] Create recovery prompt templates
- [ ] Implement validation before retry

### Task 7: Error Categorization
- [ ] Build error classifier:
  ```python
  def _categorize_error(self, error_message: str) -> str:
      """Categorize SQL error for targeted recovery"""
      
      error_patterns = {
          'SYNTAX_ERROR': [
              r'syntax error',
              r'unexpected token',
              r'parse error'
          ],
          'MISSING_COLUMN': [
              r'column .* does not exist',
              r'unknown column',
              r'no such column'
          ],
          'MISSING_TABLE': [
              r'table .* does not exist',
              r'relation .* does not exist',
              r'no such table'
          ],
          'DATA_TYPE_MISMATCH': [
              r'type mismatch',
              r'cannot convert',
              r'invalid input syntax'
          ],
          'AMBIGUOUS_COLUMN': [
              r'ambiguous column',
              r'column reference .* is ambiguous'
          ],
          'AGGREGATION_ERROR': [
              r'must appear in the GROUP BY',
              r'aggregate function'
          ],
          'PERMISSION_ERROR': [
              r'permission denied',
              r'access denied'
          ]
      }
      
      error_lower = error_message.lower()
      
      for error_type, patterns in error_patterns.items():
          for pattern in patterns:
              if re.search(pattern, error_lower):
                  return error_type
                  
      return 'UNKNOWN_ERROR'
  ```
- [ ] Add pattern matching for common errors
- [ ] Include database-specific error formats
- [ ] Log unrecognized errors for improvement

### Task 8: Integration Helpers
- [ ] Create utility functions:
  ```python
  def extract_product_metadata(all_resources: Dict) -> Dict:
      """Extract product aliases from metadata MCP"""
      for server_name, server_data in all_resources.items():
          if 'product_aliases' in server_data.get('resources', {}):
              return server_data['resources']['product_aliases']
      return {}
  
  def extract_column_mappings(all_resources: Dict) -> Dict:
      """Extract column mappings from metadata MCP"""
      for server_name, server_data in all_resources.items():
          if 'column_mappings' in server_data.get('resources', {}):
              return server_data['resources']['column_mappings']
      return {}
  
  def resolve_entity(
      entity: str,
      metadata: Dict,
      entity_type: str = 'product'
  ) -> Optional[str]:
      """Resolve user term to database value"""
      if entity_type == 'product':
          for alias_key, alias_data in metadata.items():
              if entity.lower() in [a.lower() for a in alias_data.get('aliases', [])]:
                  return alias_data.get('database_references', {}).get('products.product_id')
      return None
  ```
- [ ] Add entity resolution functions
- [ ] Create mapping translators
- [ ] Build schema extractors

## Quality Assurance

### Testing Requirements

1. **Unit Tests** (`tests/test_llm_sql_generator.py`):
   - [ ] Test prompt building with various inputs
   - [ ] Test response parsing strategies
   - [ ] Test SQL validation logic
   - [ ] Test error categorization
   - [ ] Test recovery flow

2. **Integration Tests**:
   - [ ] Test with real LLM responses
   - [ ] Test entity resolution end-to-end
   - [ ] Test error recovery with real errors
   - [ ] Test with multiple resource sets

3. **Test Scenarios**:
   ```python
   test_cases = [
       {
           "query": "sales for abracadabra this month",
           "expected_resolution": {"abracadabra": "product_id = 123"},
           "expected_mapping": {"this month": "DATE_TRUNC..."}
       },
       {
           "query": "average order value last quarter",
           "expected_aggregation": "AVG(total_amount)",
           "expected_timeframe": "3 months ago"
       }
   ]
   ```

### Code Review Checklist
- [ ] All LLM calls have timeout handling
- [ ] Response parsing handles edge cases
- [ ] SQL validation is comprehensive
- [ ] Recovery attempts are logged
- [ ] No SQL injection vulnerabilities
- [ ] Entity resolution is case-insensitive

### Performance Considerations
- LLM response time < 2 seconds
- Validation time < 100ms
- Recovery success rate > 70% (or complete failure)
- Prompt size < 4000 tokens
- Fresh metadata fetch on every request (no cache)

### Security Requirements
- [ ] Validate all SQL before execution
- [ ] Block dangerous SQL keywords
- [ ] Sanitize user input in prompts
- [ ] Log all generated SQL
- [ ] No credentials in prompts

## Junior Developer Support

### Common Pitfalls

1. **Prompt Too Long**
   - Problem: Exceeds LLM token limit
   - Solution: Truncate less important sections
   - Monitor: Token count before sending

2. **JSON Parsing Fails**
   - Problem: LLM returns malformed JSON
   - Solution: Use fallback parsing strategies
   - Debug: Log raw LLM responses

3. **Entity Not Resolved**
   - Problem: Alias not in metadata
   - Solution: Fallback to literal value
   - Check: Log unresolved entities

4. **Infinite Recovery Loop**
   - Problem: Recovery keeps failing
   - Solution: Limit retry attempts
   - Safeguard: MAX_RETRY_ATTEMPTS

### Troubleshooting Guide

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| SQL syntax errors | Bad prompt | Improve examples in prompt |
| Wrong table names | Schema not in prompt | Include full schema |
| Missing columns | Mappings incomplete | Update metadata |
| Slow generation | Prompt too large | Optimize prompt size |
| Low confidence | Ambiguous query | Request clarification |

### Reference Links
- [Prompt Engineering Guide](https://www.promptingguide.ai/)
- [SQL Parser Documentation](https://sqlparse.readthedocs.io/)
- [OpenRouter API Docs](https://openrouter.ai/docs)
- [Regex101 for Testing](https://regex101.com/)

### Code Style Guidelines
```python
# Prompt formatting
prompt = f"""
Clear section headers
{variable_content}
Consistent indentation
"""

# Response handling
try:
    response = parse_response(text)
except ParseError:
    response = fallback_parse(text)
    
# Logging SQL generation
logger.info(
    "sql_generated",
    query=user_query[:100],
    sql_length=len(sql_query),
    confidence=response.confidence
)
```

### Review Checkpoints
1. After prompt template creation
2. Before LLM integration
3. After validation implementation
4. Before Phase 4 integration

## Deliverables

### Files to Create
1. `fastapi_server/llm_sql_generator.py` (300-400 lines)
2. `fastapi_server/prompt_templates.py` (150-200 lines)
3. `fastapi_server/sql_validator.py` (200 lines)
4. `fastapi_server/recovery_handler.py` (150 lines)

### Documentation Updates
- [ ] Document prompt structure
- [ ] Add SQL generation examples
- [ ] Create error recovery guide

### Configuration Changes
- [ ] Add LLM retry settings
- [ ] Configure validation rules
- [ ] Set recovery attempt limits

## Completion Checklist

### Core Implementation
- [ ] SQL generator class complete
- [ ] Prompt building functional
- [ ] Response parsing works
- [ ] Validation implemented
- [ ] Recovery handler ready
- [ ] Entity resolution working

### Quality Gates
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Security review complete
- [ ] Performance targets met
- [ ] Documentation updated

### Handoff to Phase 4
- [ ] Generator callable from orchestrator
- [ ] Response format documented
- [ ] Error types defined
- [ ] Test queries ready

## Validation Commands

```bash
# Test SQL generation standalone
python -c "
from fastapi_server.llm_sql_generator import LLMSQLGenerator
import asyncio

async def test():
    # Mock LLM client
    class MockLLM:
        async def generate(self, prompt):
            return '{\"sql_query\": \"SELECT * FROM products\", \"explanation\": \"Test\"}'
    
    generator = LLMSQLGenerator(MockLLM())
    
    # Test resources
    resources = {
        'metadata_mcp': {
            'priority': 1,
            'resources': {
                'product_aliases': {'test': {'canonical_id': '123'}}
            }
        }
    }
    
    response = await generator.generate_sql('test query', resources)
    print(f'Generated SQL: {response.sql_query}')

asyncio.run(test())
"

# Run unit tests
pytest tests/test_llm_sql_generator.py -v

# Test SQL validation
python -c "
from fastapi_server.sql_validator import SQLValidator
validator = SQLValidator()
result = validator.validate('SELECT * FROM products', {})
print(f'Valid: {result.is_valid}')
"

# Check imports
python -c "
from fastapi_server.llm_sql_generator import LLMSQLGenerator
from fastapi_server.sql_validator import SQLValidator
from fastapi_server.recovery_handler import RecoveryHandler
print('All imports successful')
"
```

## Time Estimate
- Prompt Templates: 30 minutes
- SQL Generator Core: 60 minutes
- Response Parsing: 45 minutes
- Validation & Recovery: 45 minutes
- Testing & Integration: 30 minutes
- **Total: 3.5 hours**

## Notes for Next Phase
Phase 4 will need:
- SQL generator instance
- Integration with orchestrator
- Connection to existing FastAPI
- End-to-end query flow