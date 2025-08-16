# Multi-MCP End-to-End Testing Strategy

**Project**: Talk-2-Tables MCP System  
**Test Framework**: Puppeteer MCP Tool  
**Created**: 2025-08-16  
**Status**: Ready for Implementation

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Testing Objectives](#testing-objectives)
3. [Test Environment Setup](#test-environment-setup)
4. [Single MCP Test Cases](#single-mcp-test-cases)
5. [Multi-MCP Cross-Reference Tests](#multi-mcp-cross-reference-tests)
6. [Failure & Resilience Testing](#failure--resilience-testing)
7. [Puppeteer Implementation Framework](#puppeteer-implementation-framework)
8. [Test Data Strategy](#test-data-strategy)
9. [Validation Framework](#validation-framework)
10. [Success Criteria](#success-criteria)
11. [Implementation Roadmap](#implementation-roadmap)

---

## System Architecture Overview

### Components Under Test
```
User Query → [Puppeteer MCP Tool] → React Frontend (localhost:3000) 
    ↓
FastAPI Backend (localhost:8001) 
    ↓
┌─────────────────────────────────────┐
│  Multi-MCP Orchestration           │
├─────────────────┬───────────────────┤
│ Database MCP    │ Product MCP       │
│ localhost:8000  │ localhost:8002    │
│ (SQLite data)   │ (Metadata)        │
│ SSE transport   │ SSE transport     │
└─────────────────┴───────────────────┘
```

### Key Business Rules
1. **Priority Rule**: Product metadata MCP takes precedence over Database MCP for overlapping data
2. **Synchronous Behavior**: FastAPI waits for both MCP responses before returning results
3. **Graceful Degradation**: System should handle individual MCP failures gracefully
4. **Data Consistency**: Product IDs must be consistent across both MCPs

---

## Testing Objectives

### Primary Goals
- **Validate Multi-MCP Communication**: Ensure FastAPI correctly orchestrates both MCPs
- **Test Priority Rule Enforcement**: Verify Product MCP data overrides Database MCP conflicts
- **Verify Cross-Reference Functionality**: Confirm data correlation between MCPs works correctly
- **Validate Error Handling**: Test system behavior when one or both MCPs fail
- **Performance Testing**: Ensure acceptable response times for multi-MCP queries

### Test Scope
- ✅ **In Scope**: E2E user workflow, MCP communication, data consistency, error handling
- ❌ **Out of Scope**: Individual MCP server unit tests, database schema validation, authentication

---

## Test Environment Setup

### Prerequisites
```bash
# 1. Start all required services (3 terminals)
# Terminal 1: Database MCP Server
python -m talk_2_tables_mcp.remote_server

# Terminal 2: Product MCP Server  
TRANSPORT=sse python scripts/start_product_server.py --port 8002

# Terminal 3: FastAPI Backend
uvicorn fastapi_server.main:app --host 0.0.0.0 --port 8001

# Terminal 4: React Frontend
cd react-chatbot && npm start
```

### Service Health Checks
```bash
# Verify all services are running
curl http://localhost:8001/health  # FastAPI Backend
curl http://localhost:3000         # React Frontend (should return HTML)

# SSE endpoints (should timeout - means they're streaming)
curl http://localhost:8000/sse     # Database MCP
curl http://localhost:8002/sse     # Product MCP
```

### Puppeteer MCP Tool Setup
```javascript
// Initialize Puppeteer MCP tool connection
const puppeteerMcp = await connectToMcp('puppeteer');

// Test configuration
const testConfig = {
    frontendUrl: 'http://localhost:3000',
    fastApiUrl: 'http://localhost:8001',
    databaseMcpUrl: 'http://localhost:8000',
    productMcpUrl: 'http://localhost:8002',
    screenshotPath: './test-screenshots/',
    timeout: 30000 // 30 seconds for complex queries
};
```

---

## Single MCP Test Cases

### Database MCP Only Tests

#### Test Case 1.1: Direct SQL Query
```javascript
const testCase_1_1 = {
    name: "Direct SQL Query Execution",
    query: "SELECT * FROM customers LIMIT 5",
    expectedMcp: "database",
    expectedFlow: [
        "User enters SQL query",
        "FastAPI detects SQL pattern",
        "Routes to Database MCP only",
        "Returns customer data"
    ],
    validation: {
        mcpCalled: "database",
        responseStructure: "Array of customer objects",
        dataFields: ["id", "name", "email", "created_at"],
        responseTime: "< 2 seconds"
    }
};
```

#### Test Case 1.2: Natural Language Database Query
```javascript
const testCase_1_2 = {
    name: "Natural Language Database Query",
    query: "How many orders were placed this month?",
    expectedMcp: "database",
    expectedFlow: [
        "User enters natural language query",
        "FastAPI uses enhanced intent detection",
        "Generates SQL query for orders table", 
        "Routes to Database MCP",
        "Returns count result"
    ],
    validation: {
        mcpCalled: "database",
        responseType: "numeric count",
        sqlGenerated: "Contains COUNT() and date filtering",
        responseTime: "< 3 seconds"
    }
};
```

#### Test Case 1.3: Database Aggregation Query
```javascript
const testCase_1_3 = {
    name: "Sales Summary Query",
    query: "Show me sales summary by product",
    expectedMcp: "database",
    expectedFlow: [
        "User requests sales aggregation",
        "FastAPI generates GROUP BY query",
        "Routes to Database MCP",
        "Returns aggregated sales data"
    ],
    validation: {
        mcpCalled: "database",
        responseStructure: "Array of product sales summaries",
        dataFields: ["product_id", "total_sales", "quantity_sold"],
        sqlPattern: "GROUP BY product_id"
    }
};
```

### Product MCP Only Tests

#### Test Case 2.1: Product Specifications Query
```javascript
const testCase_2_1 = {
    name: "Product Technical Specifications",
    query: "What are the technical specifications for iPhone 15?",
    expectedMcp: "product",
    expectedFlow: [
        "User requests product specs",
        "FastAPI identifies product metadata request",
        "Routes to Product MCP only",
        "Returns detailed specifications"
    ],
    validation: {
        mcpCalled: "product",
        responseStructure: "Product object with specifications",
        dataFields: ["name", "model", "specifications", "features"],
        responseTime: "< 2 seconds"
    }
};
```

#### Test Case 2.2: Supplier Filtering
```javascript
const testCase_2_2 = {
    name: "Products by Supplier",
    query: "List all products from Apple supplier",
    expectedMcp: "product",
    expectedFlow: [
        "User filters by supplier",
        "FastAPI identifies catalog filtering request",
        "Routes to Product MCP",
        "Returns filtered product list"
    ],
    validation: {
        mcpCalled: "product",
        responseStructure: "Array of Apple products",
        filterApplied: "supplier === 'Apple'",
        dataCompleteness: "All Apple products included"
    }
};
```

#### Test Case 2.3: Category-Based Query
```javascript
const testCase_2_3 = {
    name: "Product Category Information",
    query: "Show me warranty information for laptops",
    expectedMcp: "product",
    expectedFlow: [
        "User requests category-specific data",
        "FastAPI identifies metadata filtering",
        "Routes to Product MCP",
        "Returns warranty details for laptop category"
    ],
    validation: {
        mcpCalled: "product",
        responseStructure: "Array of laptop warranty information",
        categoryFilter: "category === 'laptops'",
        dataFields: ["product_name", "warranty_period", "coverage_details"]
    }
};
```

---

## Multi-MCP Cross-Reference Tests

### Test Case 3.1: Product Sales Analysis (CRITICAL)
```javascript
const testCase_3_1 = {
    name: "iPhone Revenue Analysis with Metadata",
    query: "Show me revenue for iPhone products sold this year with technical specifications",
    expectedMcps: ["product", "database"],
    expectedFlow: [
        "1. FastAPI identifies need for both MCPs",
        "2. Product MCP: Query iPhone products and specifications",
        "3. Database MCP: Query sales data for iPhone product IDs", 
        "4. FastAPI: Merge metadata with sales data",
        "5. Apply priority rule: Product MCP data takes precedence",
        "6. Return combined response to frontend"
    ],
    validation: {
        bothMcpsCalled: true,
        responseStructure: {
            products: "Array with iPhone models and specs",
            salesData: "Revenue calculations by product",
            combinedData: "Products with sales performance"
        },
        priorityRuleApplied: {
            productNames: "From Product MCP (more detailed)",
            specifications: "From Product MCP only",
            salesFigures: "From Database MCP only"
        },
        dataConsistency: {
            productIds: "Consistent between MCPs",
            noOrphans: "All products have matching sales records"
        },
        responseTime: "< 5 seconds"
    }
};
```

### Test Case 3.2: Supplier Performance Report
```javascript
const testCase_3_2 = {
    name: "Supplier Revenue and Product Analysis",
    query: "Which supplier has the highest revenue and what are their complete product specifications?",
    expectedMcps: ["database", "product"],
    expectedFlow: [
        "1. Database MCP: Calculate revenue by supplier from sales data",
        "2. Product MCP: Get detailed supplier information and product specs",
        "3. FastAPI: Combine financial performance with supplier metadata",
        "4. Apply priority rule for supplier names and details"
    ],
    validation: {
        bothMcpsCalled: true,
        responseStructure: {
            supplierRankings: "Ordered by revenue from Database MCP",
            supplierDetails: "Detailed info from Product MCP",
            productPortfolio: "Complete product specs per supplier"
        },
        priorityRuleApplied: {
            supplierNames: "Product MCP overrides database names",
            supplierDetails: "Product MCP metadata preferred",
            revenueCalculations: "From Database MCP only"
        },
        businessLogic: {
            topSupplierIdentified: true,
            completeProductCatalog: true,
            revenueAccuracy: "Verified against sales records"
        }
    }
};
```

### Test Case 3.3: Inventory Validation
```javascript
const testCase_3_3 = {
    name: "Product Catalog vs Sales History Validation", 
    query: "Are there any products in our catalog that have no sales history?",
    expectedMcps: ["product", "database"],
    expectedFlow: [
        "1. Product MCP: Get complete product catalog",
        "2. Database MCP: Get all products with sales records",
        "3. FastAPI: Identify orphaned products (catalog but no sales)",
        "4. FastAPI: Identify orphaned sales (sales but no catalog entry)"
    ],
    validation: {
        bothMcpsCalled: true,
        responseStructure: {
            catalogProducts: "Complete product list from Product MCP",
            salesProducts: "Products with sales from Database MCP",
            orphanedCatalog: "Products with no sales history",
            orphanedSales: "Sales records with no catalog entry"
        },
        dataIntegrityCheck: {
            productIdConsistency: "IDs format matches between MCPs",
            orphanDetection: "Correctly identifies mismatched records",
            reportAccuracy: "Counts match manual verification"
        },
        businessValue: {
            inventoryInsights: "Identifies unsold products",
            dataQualityMetrics: "Highlights data inconsistencies"
        }
    }
};
```

### Test Case 3.4: Complex Query with Priority Rule Testing
```javascript
const testCase_3_4 = {
    name: "Priority Rule Enforcement Test",
    query: "Show me product details and sales for items where product names differ between systems",
    expectedMcps: ["product", "database"],
    testData: {
        // Intentionally conflicting data to test priority rules
        conflictingProducts: [
            {
                product_id: "IPHONE_15_PRO",
                databaseName: "iPhone 15 Pro",
                productMcpName: "iPhone 15 Pro Max 256GB Titanium" // More detailed
            }
        ]
    },
    expectedFlow: [
        "1. Query both MCPs for product information",
        "2. Detect naming conflicts for same product_id",
        "3. Apply priority rule: Use Product MCP names",
        "4. Merge sales data with preferred product names"
    ],
    validation: {
        priorityRuleEnforced: {
            productNames: "Product MCP names used in final response",
            specifications: "Product MCP specs included",
            salesData: "Database MCP sales data preserved"
        },
        conflictResolution: {
            conflictsDetected: "System identifies naming differences",
            resolutionLogged: "Priority rule application logged",
            userTransparency: "Clear indication of data sources"
        }
    }
};
```

---

## Failure & Resilience Testing

### Test Case 4.1: Database MCP Failure
```javascript
const testCase_4_1 = {
    name: "Database MCP Unavailable",
    setup: "Kill Database MCP process during test execution",
    query: "Show me iPhone sales data with product specifications",
    expectedBehavior: "Graceful failure with partial results",
    expectedFlow: [
        "1. User submits query requiring both MCPs",
        "2. Product MCP responds successfully",
        "3. Database MCP connection fails",
        "4. FastAPI detects failure and returns partial results",
        "5. Frontend displays available data with error message"
    ],
    validation: {
        partialResults: {
            productData: "Available from Product MCP",
            salesData: "Unavailable - clear error message",
            userExperience: "Informative error, not system crash"
        },
        errorHandling: {
            errorMessage: "User-friendly explanation",
            systemStability: "No application crash",
            recovery: "System recovers when MCP restored"
        },
        logging: {
            mcpFailureLogged: "Database MCP connection error logged",
            partialResponseLogged: "Partial result delivery logged"
        }
    }
};
```

### Test Case 4.2: Product MCP Failure  
```javascript
const testCase_4_2 = {
    name: "Product MCP Unavailable",
    setup: "Kill Product MCP process during test execution",
    query: "What are iPhone specifications and how many were sold?",
    expectedBehavior: "Fallback to database data with limitations notice",
    expectedFlow: [
        "1. User requests product specs and sales data",
        "2. Database MCP responds with basic product info and sales",
        "3. Product MCP connection fails", 
        "4. FastAPI returns database data with metadata limitation notice",
        "5. Frontend shows available data with clear limitation explanation"
    ],
    validation: {
        fallbackBehavior: {
            basicProductInfo: "Available from database",
            salesData: "Complete from Database MCP",
            missingSpecs: "Clear indication of unavailable detailed specs"
        },
        userCommunication: {
            limitationNotice: "Explains reduced data richness",
            retryOption: "Suggests trying again later",
            functionalityMaintained: "Core query still answered"
        }
    }
};
```

### Test Case 4.3: Both MCPs Failure
```javascript
const testCase_4_3 = {
    name: "Complete MCP System Failure",
    setup: "Kill both MCP processes",
    query: "Show me any product or sales information",
    expectedBehavior: "Clear system unavailability message",
    expectedFlow: [
        "1. User submits any query requiring MCP data",
        "2. FastAPI attempts to connect to both MCPs",
        "3. Both connections fail",
        "4. FastAPI returns comprehensive error response",
        "5. Frontend displays system maintenance message"
    ],
    validation: {
        systemBehavior: {
            noPartialResults: "No incomplete data returned",
            clearErrorMessage: "Explains system is temporarily unavailable",
            noSystemCrash: "Application remains stable"
        },
        userExperience: {
            maintenanceMessage: "Professional unavailability notice",
            retryGuidance: "Instructions for when to retry",
            supportContact: "Alternative support options if needed"
        }
    }
};
```

### Test Case 4.4: Network Latency Simulation
```javascript
const testCase_4_4 = {
    name: "High Network Latency Impact",
    setup: "Simulate 2-second delay to each MCP",
    query: "Complex query requiring both MCPs",
    expectedBehavior: "Increased response time but successful completion",
    validation: {
        performanceImpact: {
            responseTime: "4-6 seconds (additive delays)",
            timeoutHandling: "No premature timeouts",
            userFeedback: "Loading indicators remain active"
        },
        systemResilience: {
            completesSuccessfully: "Query finishes despite delays",
            dataIntegrity: "Results remain accurate",
            concurrentQueries: "Other queries not affected"
        }
    }
};
```

---

## Puppeteer Implementation Framework

### Core Test Infrastructure
```javascript
/**
 * Puppeteer MCP E2E Test Framework
 * Comprehensive implementation for multi-MCP testing
 */

class MultiMcpTestFramework {
    constructor(config) {
        this.config = {
            frontendUrl: 'http://localhost:3000',
            fastApiUrl: 'http://localhost:8001',
            databaseMcpUrl: 'http://localhost:8000',
            productMcpUrl: 'http://localhost:8002',
            screenshotPath: './test-screenshots/',
            timeout: 30000,
            ...config
        };
        this.networkActivity = [];
        this.mcpCalls = [];
    }

    async setup() {
        console.log('🚀 Setting up Multi-MCP E2E Test Environment');
        
        // 1. Navigate to frontend
        await this.navigateToFrontend();
        
        // 2. Setup network monitoring
        await this.setupNetworkMonitoring();
        
        // 3. Verify system health
        await this.verifySystemHealth();
        
        // 4. Take baseline screenshot
        await this.takeScreenshot('baseline-system');
        
        console.log('✅ Test environment ready');
    }

    async navigateToFrontend() {
        console.log(`📍 Navigating to ${this.config.frontendUrl}`);
        await this.puppeteerNavigate(this.config.frontendUrl);
        
        // Wait for React app to load
        await this.waitForElement('.chat-interface', { timeout: 10000 });
        
        // Verify key UI elements are present
        const elements = await Promise.all([
            this.waitForElement('#query-input'),
            this.waitForElement('#send-button'),
            this.waitForElement('.response-container')
        ]);
        
        console.log('✅ Frontend loaded successfully');
        return elements.every(el => el !== null);
    }

    async setupNetworkMonitoring() {
        console.log('🔍 Setting up network activity monitoring');
        
        // Monitor all relevant endpoints
        const endpoints = [
            this.config.fastApiUrl + '/chat/completions',
            this.config.databaseMcpUrl + '/sse',
            this.config.productMcpUrl + '/sse'
        ];
        
        // Setup request interception
        await this.interceptRequests(endpoints);
        
        // Reset monitoring arrays
        this.networkActivity = [];
        this.mcpCalls = [];
        
        console.log('✅ Network monitoring active');
    }

    async verifySystemHealth() {
        console.log('🔧 Verifying system health before testing');
        
        const healthChecks = await Promise.allSettled([
            this.checkFastApiHealth(),
            this.checkMcpConnectivity('database'),
            this.checkMcpConnectivity('product')
        ]);
        
        const results = healthChecks.map((check, index) => ({
            service: ['FastAPI', 'Database MCP', 'Product MCP'][index],
            status: check.status === 'fulfilled' ? '✅' : '❌',
            details: check.status === 'fulfilled' ? check.value : check.reason
        }));
        
        console.table(results);
        
        const allHealthy = healthChecks.every(check => check.status === 'fulfilled');
        if (!allHealthy) {
            throw new Error('System health check failed - ensure all services are running');
        }
        
        return results;
    }

    async runSingleMcpTest(testCase) {
        console.log(`🧪 Running Single MCP Test: ${testCase.name}`);
        
        const startTime = Date.now();
        
        try {
            // 1. Clear previous state
            await this.clearChatHistory();
            
            // 2. Submit query
            await this.submitQuery(testCase.query);
            
            // 3. Wait for response
            const response = await this.waitForResponse();
            const endTime = Date.now();
            
            // 4. Validate MCP routing
            const mcpActivity = this.getMcpActivity();
            const routingCorrect = mcpActivity.includes(testCase.expectedMcp) &&
                                   mcpActivity.length === 1;
            
            // 5. Validate response structure
            const responseValid = await this.validateResponseStructure(
                response, 
                testCase.validation
            );
            
            // 6. Performance check
            const responseTime = endTime - startTime;
            const performanceOk = responseTime < (testCase.validation.responseTime || 5000);
            
            const result = {
                testCase: testCase.name,
                status: routingCorrect && responseValid && performanceOk ? 'PASS' : 'FAIL',
                mcpCalled: mcpActivity,
                responseTime: `${responseTime}ms`,
                response: response,
                validations: {
                    routing: routingCorrect,
                    structure: responseValid,
                    performance: performanceOk
                }
            };
            
            await this.takeScreenshot(`single-mcp-${testCase.name.replace(/\s+/g, '-')}`);
            
            console.log(`${result.status === 'PASS' ? '✅' : '❌'} ${testCase.name}: ${result.status}`);
            return result;
            
        } catch (error) {
            console.error(`❌ Single MCP Test Failed: ${testCase.name}`, error);
            await this.takeScreenshot(`error-single-mcp-${testCase.name.replace(/\s+/g, '-')}`);
            throw error;
        }
    }

    async runMultiMcpTest(testCase) {
        console.log(`🔄 Running Multi-MCP Test: ${testCase.name}`);
        
        const startTime = Date.now();
        
        try {
            // 1. Clear previous state
            await this.clearChatHistory();
            
            // 2. Reset MCP monitoring
            this.mcpCalls = [];
            
            // 3. Submit complex query
            await this.submitQuery(testCase.query);
            
            // 4. Monitor both MCP calls
            const mcpResponses = await this.waitForMultipleMcpResponses(
                testCase.expectedMcps,
                this.config.timeout
            );
            
            // 5. Wait for combined response
            const finalResponse = await this.waitForResponse();
            const endTime = Date.now();
            
            // 6. Validate MCP coordination
            const mcpActivity = this.getMcpActivity();
            const bothMcpsCalled = testCase.expectedMcps.every(mcp => 
                mcpActivity.includes(mcp)
            );
            
            // 7. Validate priority rule application
            const priorityRuleApplied = await this.validatePriorityRule(
                finalResponse, 
                testCase.validation.priorityRuleApplied
            );
            
            // 8. Validate data consistency
            const dataConsistent = await this.validateDataConsistency(
                finalResponse,
                testCase.validation.dataConsistency
            );
            
            // 9. Performance validation
            const responseTime = endTime - startTime;
            const performanceOk = responseTime < testCase.validation.responseTime;
            
            const result = {
                testCase: testCase.name,
                status: bothMcpsCalled && priorityRuleApplied && dataConsistent && performanceOk ? 'PASS' : 'FAIL',
                mcpsCalled: mcpActivity,
                mcpResponses: mcpResponses,
                finalResponse: finalResponse,
                responseTime: `${responseTime}ms`,
                validations: {
                    bothMcpsCalled: bothMcpsCalled,
                    priorityRule: priorityRuleApplied,
                    dataConsistency: dataConsistent,
                    performance: performanceOk
                }
            };
            
            await this.takeScreenshot(`multi-mcp-${testCase.name.replace(/\s+/g, '-')}`);
            
            console.log(`${result.status === 'PASS' ? '✅' : '❌'} ${testCase.name}: ${result.status}`);
            return result;
            
        } catch (error) {
            console.error(`❌ Multi-MCP Test Failed: ${testCase.name}`, error);
            await this.takeScreenshot(`error-multi-mcp-${testCase.name.replace(/\s+/g, '-')}`);
            throw error;
        }
    }

    async runResilienceTest(testCase) {
        console.log(`🛡️ Running Resilience Test: ${testCase.name}`);
        
        try {
            // 1. Setup failure condition
            await this.setupFailureCondition(testCase.setup);
            
            // 2. Submit query
            await this.submitQuery(testCase.query);
            
            // 3. Wait for error handling
            const errorResponse = await this.waitForErrorOrResponse();
            
            // 4. Validate graceful failure
            const gracefulFailure = await this.validateGracefulFailure(
                errorResponse,
                testCase.validation
            );
            
            // 5. Test system recovery
            await this.restoreFailureCondition(testCase.setup);
            const recoverySuccessful = await this.testSystemRecovery();
            
            const result = {
                testCase: testCase.name,
                status: gracefulFailure && recoverySuccessful ? 'PASS' : 'FAIL',
                errorResponse: errorResponse,
                validations: {
                    gracefulFailure: gracefulFailure,
                    recovery: recoverySuccessful
                }
            };
            
            await this.takeScreenshot(`resilience-${testCase.name.replace(/\s+/g, '-')}`);
            
            console.log(`${result.status === 'PASS' ? '✅' : '❌'} ${testCase.name}: ${result.status}`);
            return result;
            
        } catch (error) {
            console.error(`❌ Resilience Test Failed: ${testCase.name}`, error);
            await this.takeScreenshot(`error-resilience-${testCase.name.replace(/\s+/g, '-')}`);
            throw error;
        }
    }

    // Helper Methods
    async submitQuery(query) {
        console.log(`💬 Submitting query: "${query}"`);
        
        await this.puppeteerFill('#query-input', query);
        await this.puppeteerClick('#send-button');
        
        // Wait for query submission to be processed
        await this.waitForElement('.loading-indicator, .response-content', { timeout: 2000 });
    }

    async waitForResponse() {
        console.log('⏳ Waiting for response...');
        
        // Wait for loading to complete and response to appear
        await this.waitForElement('.response-content', { timeout: this.config.timeout });
        
        // Extract response data
        const responseText = await this.puppeteerEvaluate(() => {
            const responseElement = document.querySelector('.response-content');
            return responseElement ? responseElement.textContent : null;
        });
        
        const responseData = await this.puppeteerEvaluate(() => {
            // Try to extract structured data if available
            const dataElement = document.querySelector('[data-response-json]');
            if (dataElement) {
                try {
                    return JSON.parse(dataElement.getAttribute('data-response-json'));
                } catch (e) {
                    return null;
                }
            }
            return null;
        });
        
        return {
            text: responseText,
            data: responseData
        };
    }

    async waitForMultipleMcpResponses(expectedMcps, timeout) {
        console.log(`🔄 Waiting for responses from MCPs: ${expectedMcps.join(', ')}`);
        
        const mcpPromises = expectedMcps.map(mcp => 
            this.waitForMcpResponse(mcp, timeout)
        );
        
        try {
            const responses = await Promise.all(mcpPromises);
            console.log(`✅ Received responses from all expected MCPs`);
            return responses;
        } catch (error) {
            console.error(`❌ Failed to receive responses from all MCPs:`, error);
            throw error;
        }
    }

    async waitForMcpResponse(mcpType, timeout) {
        const startTime = Date.now();
        
        while (Date.now() - startTime < timeout) {
            const activity = this.getMcpActivity();
            if (activity.includes(mcpType)) {
                return { mcp: mcpType, timestamp: Date.now() };
            }
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        throw new Error(`Timeout waiting for ${mcpType} MCP response`);
    }

    getMcpActivity() {
        // Analyze network activity to determine which MCPs were called
        const mcpCalls = this.networkActivity.filter(activity => 
            activity.url.includes(':8000') || activity.url.includes(':8002')
        );
        
        const mcpTypes = mcpCalls.map(call => {
            if (call.url.includes(':8000')) return 'database';
            if (call.url.includes(':8002')) return 'product';
            return 'unknown';
        });
        
        return [...new Set(mcpTypes)]; // Remove duplicates
    }

    async validatePriorityRule(response, priorityValidation) {
        console.log('🔍 Validating priority rule application...');
        
        if (!priorityValidation) return true;
        
        // Check if Product MCP data takes precedence
        const hasProductNames = priorityValidation.productNames && 
                               response.data && 
                               response.data.products &&
                               response.data.products.every(p => p.source === 'product-mcp' || p.name.includes('detailed'));
        
        const hasProductSpecs = priorityValidation.specifications &&
                               response.data &&
                               response.data.products &&
                               response.data.products.some(p => p.specifications);
        
        const hasDatabaseSales = priorityValidation.salesFigures &&
                                response.data &&
                                response.data.sales;
        
        return hasProductNames || hasProductSpecs || hasDatabaseSales;
    }

    async validateDataConsistency(response, consistencyValidation) {
        console.log('🔍 Validating data consistency...');
        
        if (!consistencyValidation) return true;
        
        const productIds = response.data?.products?.map(p => p.id) || [];
        const salesProductIds = response.data?.sales?.map(s => s.product_id) || [];
        
        // Check for consistent product IDs
        const idsConsistent = consistencyValidation.productIds &&
                             productIds.length > 0 &&
                             salesProductIds.length > 0 &&
                             productIds.every(id => salesProductIds.includes(id));
        
        // Check for orphaned records
        const noOrphans = consistencyValidation.noOrphans &&
                         productIds.length === salesProductIds.length;
        
        return idsConsistent || noOrphans;
    }

    async validateGracefulFailure(errorResponse, validation) {
        console.log('🛡️ Validating graceful failure handling...');
        
        const hasUserFriendlyMessage = errorResponse.text &&
                                      !errorResponse.text.includes('500 Internal Server Error') &&
                                      !errorResponse.text.includes('Connection refused');
        
        const systemStable = !errorResponse.text.includes('Application crashed') &&
                            !errorResponse.text.includes('Uncaught exception');
        
        const hasPartialResults = validation.partialResults &&
                                 errorResponse.data &&
                                 (errorResponse.data.products || errorResponse.data.sales);
        
        return hasUserFriendlyMessage && systemStable && (hasPartialResults || !validation.partialResults);
    }

    async clearChatHistory() {
        console.log('🧹 Clearing chat history...');
        
        // Click clear button if it exists
        const clearButton = await this.puppeteerEvaluate(() => 
            document.querySelector('.clear-chat-button, [data-testid="clear-chat"]')
        );
        
        if (clearButton) {
            await this.puppeteerClick('.clear-chat-button, [data-testid="clear-chat"]');
        } else {
            // Refresh page to clear state
            await this.puppeteerNavigate(this.config.frontendUrl);
            await this.waitForElement('.chat-interface', { timeout: 10000 });
        }
    }

    async takeScreenshot(filename) {
        const fullPath = `${this.config.screenshotPath}${filename}-${Date.now()}.png`;
        console.log(`📸 Taking screenshot: ${fullPath}`);
        
        try {
            await this.puppeteerScreenshot(fullPath);
            return fullPath;
        } catch (error) {
            console.error(`Failed to take screenshot: ${error.message}`);
            return null;
        }
    }

    // Puppeteer MCP Tool Integration Methods
    async puppeteerNavigate(url) {
        // Implementation using Puppeteer MCP tool
        // This would call the actual MCP tool methods
        console.log(`Navigating to: ${url}`);
        // await mcpToolCall('puppeteer_navigate', { url });
    }

    async puppeteerClick(selector) {
        // Implementation using Puppeteer MCP tool
        console.log(`Clicking: ${selector}`);
        // await mcpToolCall('puppeteer_click', { selector });
    }

    async puppeteerFill(selector, value) {
        // Implementation using Puppeteer MCP tool
        console.log(`Filling ${selector} with: ${value}`);
        // await mcpToolCall('puppeteer_fill', { selector, value });
    }

    async puppeteerScreenshot(filename) {
        // Implementation using Puppeteer MCP tool
        console.log(`Taking screenshot: ${filename}`);
        // await mcpToolCall('puppeteer_screenshot', { name: filename });
    }

    async puppeteerEvaluate(script) {
        // Implementation using Puppeteer MCP tool
        console.log(`Evaluating script: ${script}`);
        // return await mcpToolCall('puppeteer_evaluate', { script });
    }

    async waitForElement(selector, options = {}) {
        // Implementation using Puppeteer MCP tool
        const timeout = options.timeout || this.config.timeout;
        console.log(`Waiting for element: ${selector} (timeout: ${timeout}ms)`);
        // return await mcpToolCall('puppeteer_waitForSelector', { selector, timeout });
    }

    async interceptRequests(urls) {
        // Implementation using Puppeteer MCP tool for request interception
        console.log(`Setting up request interception for: ${urls.join(', ')}`);
        // This would setup network monitoring through the MCP tool
    }

    async checkFastApiHealth() {
        // Health check implementation
        console.log('Checking FastAPI health...');
        // return await fetch(`${this.config.fastApiUrl}/health`);
    }

    async checkMcpConnectivity(mcpType) {
        // MCP connectivity check
        console.log(`Checking ${mcpType} MCP connectivity...`);
        // Implementation depends on MCP health endpoints
    }
}
```

### Test Execution Script
```javascript
/**
 * Main test execution script
 * Orchestrates all test phases
 */

async function executeMultiMcpTestSuite() {
    const framework = new MultiMcpTestFramework();
    
    console.log('🎯 Starting Multi-MCP E2E Test Suite');
    console.log('=' .repeat(50));
    
    try {
        // Phase 1: Setup
        await framework.setup();
        
        // Phase 2: Single MCP Tests
        console.log('\n📋 Phase 1: Single MCP Tests');
        console.log('-'.repeat(30));
        
        const singleMcpResults = [];
        
        for (const testCase of singleMcpTestCases) {
            const result = await framework.runSingleMcpTest(testCase);
            singleMcpResults.push(result);
        }
        
        // Phase 3: Multi-MCP Tests
        console.log('\n🔄 Phase 2: Multi-MCP Cross-Reference Tests');
        console.log('-'.repeat(40));
        
        const multiMcpResults = [];
        
        for (const testCase of multiMcpTestCases) {
            const result = await framework.runMultiMcpTest(testCase);
            multiMcpResults.push(result);
        }
        
        // Phase 4: Resilience Tests
        console.log('\n🛡️ Phase 3: Resilience & Failure Tests');
        console.log('-'.repeat(35));
        
        const resilienceResults = [];
        
        for (const testCase of resilienceTestCases) {
            const result = await framework.runResilienceTest(testCase);
            resilienceResults.push(result);
        }
        
        // Generate Test Report
        const report = generateTestReport({
            singleMcp: singleMcpResults,
            multiMcp: multiMcpResults,
            resilience: resilienceResults
        });
        
        console.log('\n📊 Test Execution Complete');
        console.log('=' .repeat(50));
        console.log(report);
        
        return report;
        
    } catch (error) {
        console.error('❌ Test suite execution failed:', error);
        throw error;
    }
}

function generateTestReport(results) {
    const totalTests = Object.values(results).flat().length;
    const passedTests = Object.values(results).flat().filter(r => r.status === 'PASS').length;
    const failedTests = totalTests - passedTests;
    
    return {
        summary: {
            total: totalTests,
            passed: passedTests,
            failed: failedTests,
            passRate: `${((passedTests / totalTests) * 100).toFixed(1)}%`
        },
        details: results,
        timestamp: new Date().toISOString()
    };
}

// Export for use
module.exports = {
    MultiMcpTestFramework,
    executeMultiMcpTestSuite
};
```

---

## Test Data Strategy

### Overlapping Data for Priority Rule Testing
```json
{
  "overlappingProducts": [
    {
      "product_id": "IPHONE_15_PRO",
      "database": {
        "name": "iPhone 15 Pro",
        "category": "Phone",
        "supplier": "Apple",
        "price": 999.99
      },
      "productMcp": {
        "name": "iPhone 15 Pro Max 256GB Titanium Natural",
        "category": "Smartphone",
        "supplier": "Apple Inc.",
        "specifications": {
          "storage": "256GB",
          "color": "Titanium Natural",
          "display": "6.7-inch Super Retina XDR",
          "camera": "48MP Main + 12MP Ultra Wide + 12MP Telephoto",
          "processor": "A17 Pro chip",
          "battery": "Up to 29 hours video playback"
        },
        "warranty": {
          "period": "1 year",
          "coverage": "Hardware defects",
          "extendedOptions": "AppleCare+ available"
        }
      }
    },
    {
      "product_id": "MACBOOK_AIR_M2",
      "database": {
        "name": "MacBook Air M2",
        "category": "Laptop",
        "supplier": "Apple"
      },
      "productMcp": {
        "name": "MacBook Air 13-inch M2 Chip 512GB SSD Space Gray",
        "category": "Ultrabook",
        "supplier": "Apple Inc.",
        "specifications": {
          "processor": "Apple M2 chip",
          "memory": "16GB unified memory",
          "storage": "512GB SSD",
          "display": "13.6-inch Liquid Retina",
          "color": "Space Gray"
        }
      }
    }
  ]
}
```

### Cross-Reference Test Data
```json
{
  "crossReferenceScenarios": {
    "productsWithSales": [
      {
        "product_id": "IPHONE_15_PRO",
        "sales_records": [
          {"order_id": "ORD001", "quantity": 2, "unit_price": 999.99, "order_date": "2024-01-15"},
          {"order_id": "ORD003", "quantity": 1, "unit_price": 999.99, "order_date": "2024-02-20"}
        ],
        "total_revenue": 2999.97,
        "units_sold": 3
      },
      {
        "product_id": "AIRPODS_PRO",
        "sales_records": [
          {"order_id": "ORD002", "quantity": 5, "unit_price": 249.99, "order_date": "2024-01-18"}
        ],
        "total_revenue": 1249.95,
        "units_sold": 5
      }
    ],
    "productsWithoutSales": [
      {
        "product_id": "IPHONE_16_CONCEPT",
        "reason": "Unreleased product",
        "expected_behavior": "Should appear in catalog but not sales reports"
      },
      {
        "product_id": "DISCONTINUED_ITEM",
        "reason": "No longer sold",
        "expected_behavior": "Should be flagged as orphaned catalog entry"
      }
    ],
    "salesWithoutProducts": [
      {
        "product_id": "LEGACY_PRODUCT_123",
        "sales_records": [
          {"order_id": "ORD999", "quantity": 1, "unit_price": 199.99, "order_date": "2023-12-01"}
        ],
        "reason": "Product removed from catalog but sales history exists",
        "expected_behavior": "Should be flagged as orphaned sales record"
      }
    ]
  }
}
```

### Performance Test Data
```json
{
  "performanceTestData": {
    "largeDatasets": {
      "products": 1000,
      "sales_records": 50000,
      "customers": 10000,
      "expected_response_time": "< 10 seconds"
    },
    "complexQueries": [
      {
        "query": "Show me revenue by product category for the top 10 customers this year with complete product specifications",
        "expected_mcps": ["database", "product"],
        "complexity": "High - requires joins across multiple tables and detailed metadata"
      }
    ],
    "concurrentLoad": {
      "simultaneous_users": 10,
      "queries_per_user": 5,
      "expected_behavior": "No degradation in individual query performance"
    }
  }
}
```

---

## Validation Framework

### Response Structure Validation
```javascript
const responseValidators = {
    
    validateSingleMcpResponse: (response, expectedMcp) => {
        const validations = [];
        
        // Check response structure
        validations.push({
            check: 'Response exists',
            passed: !!response,
            details: response ? 'Response received' : 'No response received'
        });
        
        // Check data format
        if (response && response.data) {
            validations.push({
                check: 'Data structure valid',
                passed: typeof response.data === 'object',
                details: `Data type: ${typeof response.data}`
            });
        }
        
        // Check MCP routing
        validations.push({
            check: `Routed to ${expectedMcp} MCP`,
            passed: response.meta && response.meta.mcp_used === expectedMcp,
            details: `MCP used: ${response.meta?.mcp_used || 'unknown'}`
        });
        
        return {
            overall: validations.every(v => v.passed),
            validations: validations
        };
    },
    
    validateMultiMcpResponse: (response, expectedMcps) => {
        const validations = [];
        
        // Check both MCPs were used
        const mcpsUsed = response.meta?.mcps_used || [];
        validations.push({
            check: 'Both MCPs called',
            passed: expectedMcps.every(mcp => mcpsUsed.includes(mcp)),
            details: `MCPs used: ${mcpsUsed.join(', ')}, Expected: ${expectedMcps.join(', ')}`
        });
        
        // Check data merge
        validations.push({
            check: 'Data successfully merged',
            passed: response.data && 
                   (response.data.products || response.data.sales) &&
                   response.data.metadata,
            details: `Data sections: ${Object.keys(response.data || {}).join(', ')}`
        });
        
        // Check priority rule application
        if (response.data && response.data.products) {
            const hasDetailedNames = response.data.products.some(p => 
                p.name.length > 20 || p.specifications
            );
            validations.push({
                check: 'Priority rule applied (Product MCP precedence)',
                passed: hasDetailedNames,
                details: hasDetailedNames ? 'Detailed product info detected' : 'Basic product info only'
            });
        }
        
        return {
            overall: validations.every(v => v.passed),
            validations: validations
        };
    },
    
    validateErrorHandling: (response, expectedErrorType) => {
        const validations = [];
        
        // Check error is user-friendly
        const hasUserFriendlyError = response.text && 
                                    !response.text.includes('500') &&
                                    !response.text.includes('Internal Server Error') &&
                                    response.text.includes('temporarily unavailable');
        
        validations.push({
            check: 'User-friendly error message',
            passed: hasUserFriendlyError,
            details: response.text ? `Message: "${response.text.substring(0, 100)}..."` : 'No error message'
        });
        
        // Check system stability
        const systemStable = !response.text.includes('crashed') &&
                            !response.text.includes('exception');
        
        validations.push({
            check: 'System remains stable',
            passed: systemStable,
            details: systemStable ? 'No crash indicators' : 'System instability detected'
        });
        
        // Check partial results if expected
        if (expectedErrorType === 'partial') {
            const hasPartialData = response.data && 
                                  (response.data.products || response.data.sales);
            validations.push({
                check: 'Partial results provided',
                passed: hasPartialData,
                details: hasPartialData ? 'Some data available' : 'No partial data'
            });
        }
        
        return {
            overall: validations.every(v => v.passed),
            validations: validations
        };
    }
};
```

### Data Consistency Validators
```javascript
const consistencyValidators = {
    
    validateProductIdConsistency: (response) => {
        if (!response.data || !response.data.products || !response.data.sales) {
            return { passed: false, reason: 'Missing product or sales data' };
        }
        
        const productIds = new Set(response.data.products.map(p => p.id));
        const salesProductIds = new Set(response.data.sales.map(s => s.product_id));
        
        const orphanedProducts = [...productIds].filter(id => !salesProductIds.has(id));
        const orphanedSales = [...salesProductIds].filter(id => !productIds.has(id));
        
        return {
            passed: orphanedProducts.length === 0 && orphanedSales.length === 0,
            productIds: productIds.size,
            salesProductIds: salesProductIds.size,
            orphanedProducts: orphanedProducts,
            orphanedSales: orphanedSales,
            details: `Products: ${productIds.size}, Sales Products: ${salesProductIds.size}, Orphaned: ${orphanedProducts.length + orphanedSales.length}`
        };
    },
    
    validatePriorityRuleApplication: (response) => {
        if (!response.data || !response.data.products) {
            return { passed: false, reason: 'No product data to validate' };
        }
        
        const detailedProducts = response.data.products.filter(p => 
            p.specifications || 
            p.name.length > 30 ||
            p.warranty ||
            p.supplier.includes('Inc.')
        );
        
        const priorityRuleApplied = detailedProducts.length > 0;
        
        return {
            passed: priorityRuleApplied,
            totalProducts: response.data.products.length,
            detailedProducts: detailedProducts.length,
            examples: detailedProducts.slice(0, 3).map(p => ({
                name: p.name,
                hasSpecs: !!p.specifications,
                hasWarranty: !!p.warranty
            })),
            details: priorityRuleApplied ? 
                `${detailedProducts.length}/${response.data.products.length} products have detailed metadata` :
                'No detailed metadata found - priority rule may not be working'
        };
    },
    
    validateDataCompleteness: (response, expectedFields) => {
        if (!response.data) {
            return { passed: false, reason: 'No data in response' };
        }
        
        const missingFields = expectedFields.filter(field => !response.data[field]);
        const extraFields = Object.keys(response.data).filter(field => !expectedFields.includes(field));
        
        return {
            passed: missingFields.length === 0,
            expectedFields: expectedFields,
            presentFields: Object.keys(response.data),
            missingFields: missingFields,
            extraFields: extraFields,
            details: missingFields.length === 0 ? 
                'All expected fields present' : 
                `Missing: ${missingFields.join(', ')}`
        };
    }
};
```

---

## Success Criteria

### Functional Requirements
```javascript
const functionalCriteria = {
    singleMcpCommunication: {
        requirement: "Individual MCP queries work correctly",
        successConditions: [
            "Database-only queries return data from Database MCP",
            "Product-only queries return data from Product MCP",
            "Response times under 3 seconds for simple queries",
            "Correct data structure in responses"
        ],
        acceptanceCriteria: "100% pass rate for single MCP test cases"
    },
    
    multiMcpOrchestration: {
        requirement: "FastAPI correctly orchestrates multiple MCPs",
        successConditions: [
            "Both MCPs called for cross-reference queries",
            "FastAPI waits for both responses before returning",
            "Data from both MCPs merged correctly",
            "Response structure includes data from both sources"
        ],
        acceptanceCriteria: "100% pass rate for multi-MCP test cases"
    },
    
    priorityRuleEnforcement: {
        requirement: "Product MCP data takes precedence over Database MCP",
        successConditions: [
            "Product names from Product MCP used in final response",
            "Product specifications only from Product MCP",
            "Supplier details from Product MCP override database",
            "Sales data from Database MCP preserved"
        ],
        acceptanceCriteria: "Priority rule correctly applied in 100% of conflicting data scenarios"
    },
    
    errorHandling: {
        requirement: "Graceful degradation when MCPs fail",
        successConditions: [
            "User-friendly error messages for MCP failures",
            "Partial results when one MCP fails",
            "System remains stable during failures",
            "Recovery when MCPs restored"
        ],
        acceptanceCriteria: "No system crashes, clear error communication in 100% of failure scenarios"
    }
};
```

### Performance Requirements
```javascript
const performanceCriteria = {
    responseTime: {
        singleMcp: "< 3 seconds",
        multiMcp: "< 5 seconds",
        complexQueries: "< 10 seconds",
        measurement: "95th percentile response time"
    },
    
    concurrency: {
        simultaneousUsers: 10,
        queriesPerUser: 5,
        acceptableDegradation: "< 20% increase in response time",
        systemStability: "No failures under concurrent load"
    },
    
    networkResilience: {
        latencyTolerance: "Functional with 2-second MCP delays",
        timeoutHandling: "Graceful timeout after 30 seconds",
        retryLogic: "Automatic retry for transient failures"
    }
};
```

### Quality Assurance Requirements
```javascript
const qualityCriteria = {
    dataIntegrity: {
        productIdConsistency: "100% consistency between MCPs",
        noDataCorruption: "No data loss during merge operations",
        orphanDetection: "Clear identification of orphaned records"
    },
    
    userExperience: {
        loadingIndicators: "Clear feedback during multi-MCP queries",
        errorCommunication: "Understandable error messages for business users",
        responsiveDesign: "Functional across different screen sizes"
    },
    
    systemReliability: {
        uptimeRequirement: "99% availability during test execution",
        memoryManagement: "No memory leaks during extended testing",
        logQuality: "Comprehensive logging for debugging"
    }
};
```

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1)
```
Day 1-2: Test Environment Setup
├── Install and configure Puppeteer MCP tool
├── Verify all services (React, FastAPI, both MCPs) are running
├── Create test data sets with overlapping products
└── Setup screenshot and logging infrastructure

Day 3-4: Single MCP Test Implementation
├── Implement database-only test cases
├── Implement product-only test cases
├── Create response validation framework
└── Basic error handling tests

Day 5: Phase 1 Validation
├── Run complete single MCP test suite
├── Fix any framework issues
├── Document baseline performance metrics
└── Phase 1 sign-off
```

### Phase 2: Multi-MCP Integration (Week 2)
```
Day 1-2: Multi-MCP Test Framework
├── Implement multi-MCP test orchestration
├── Create network monitoring for both MCPs
├── Build priority rule validation logic
└── Implement data consistency validators

Day 3-4: Complex Test Cases
├── Product sales analysis test implementation
├── Supplier performance report testing
├── Inventory validation test cases
└── Cross-reference data integrity tests

Day 5: Phase 2 Validation
├── Run complete multi-MCP test suite
├── Validate priority rule enforcement
├── Performance testing and optimization
└── Phase 2 sign-off
```

### Phase 3: Resilience & Production Readiness (Week 3)
```
Day 1-2: Failure Testing
├── Implement MCP failure simulation
├── Create graceful degradation tests
├── Network latency simulation
└── Recovery testing framework

Day 3-4: Performance & Load Testing
├── Concurrent user simulation
├── Large dataset performance testing
├── Response time validation
└── System stability under load

Day 5: Final Validation
├── Complete test suite execution
├── Performance benchmarking
├── Test report generation
└── Production readiness assessment
```

### Phase 4: Continuous Integration (Week 4)
```
Day 1-2: Automation
├── Integrate tests into CI/CD pipeline
├── Automated test execution scripts
├── Test result reporting automation
└── Failure notification system

Day 3-4: Documentation & Training
├── Complete test documentation
├── Create troubleshooting guides
├── Team training on test execution
└── Maintenance procedures

Day 5: Deployment
├── Production test environment setup
├── Final test execution validation
├── Go-live support
└── Post-deployment monitoring
```

---

## Test Execution Commands

### Manual Test Execution
```bash
# 1. Start all services
./start-all-services.sh

# 2. Run test suite
npm run test:e2e:multi-mcp

# 3. Generate report
npm run test:report

# 4. Cleanup
./cleanup-test-environment.sh
```

### Automated CI/CD Integration
```yaml
# .github/workflows/multi-mcp-e2e-tests.yml
name: Multi-MCP E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v2
      
    - name: Setup Node.js
      uses: actions/setup-node@v2
      with:
        node-version: '18'
        
    - name: Setup Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: |
        npm install
        pip install -e ".[dev,fastapi]"
        
    - name: Start test environment
      run: |
        ./scripts/start-test-environment.sh
        
    - name: Run E2E tests
      run: |
        npm run test:e2e:multi-mcp
        
    - name: Upload test results
      uses: actions/upload-artifact@v2
      with:
        name: test-results
        path: test-results/
        
    - name: Upload screenshots
      uses: actions/upload-artifact@v2
      with:
        name: test-screenshots
        path: test-screenshots/
```

---

## Troubleshooting Guide

### Common Issues and Solutions

#### Service Startup Issues
```bash
# Issue: MCP servers not responding
# Solution: Check port availability and restart services
netstat -tulpn | grep -E "8000|8001|8002|3000"
pkill -f "mcp"
./start-all-services.sh

# Issue: FastAPI can't connect to MCPs
# Solution: Verify MCP health endpoints
curl http://localhost:8000/sse  # Should timeout (streaming)
curl http://localhost:8002/sse  # Should timeout (streaming)
```

#### Test Execution Issues
```bash
# Issue: Puppeteer MCP tool connection fails
# Solution: Verify MCP tool is available
which mcp-server-puppeteer
npx @modelcontextprotocol/server-puppeteer --version

# Issue: Network monitoring not capturing MCP calls
# Solution: Enable request interception debugging
DEBUG=puppeteer:* npm run test:e2e:multi-mcp
```

#### Data Consistency Issues
```bash
# Issue: Product IDs don't match between MCPs
# Solution: Reset test data to consistent state
python scripts/setup_test_db.py
python scripts/setup_product_catalog.py

# Issue: Priority rule not working
# Solution: Verify Product MCP has more detailed data
cat test_data/products.json | jq '.[] | select(.specifications)'
```

---

## Appendices

### A. Test Data Files
- `test_data/consistent_products.json` - Products with matching IDs across MCPs
- `test_data/conflicting_products.json` - Products with different names/details for priority testing
- `test_data/orphaned_data.json` - Orphaned records for consistency testing
- `test_data/large_dataset.json` - Performance testing data

### B. Configuration Files
- `test_config/puppeteer_config.json` - Puppeteer MCP tool configuration
- `test_config/mcp_endpoints.json` - MCP endpoint configurations  
- `test_config/test_timeouts.json` - Timeout configurations for different test types

### C. Reference Screenshots
- `reference_screenshots/baseline_ui.png` - Expected UI state
- `reference_screenshots/loading_state.png` - Loading indicators
- `reference_screenshots/error_state.png` - Error message examples

---

**Document Status**: Ready for Implementation  
**Next Action**: Begin Phase 1 implementation  
**Owner**: Test Engineering Team  
**Review Date**: Upon completion of each phase

---

*This document serves as the comprehensive reference for implementing end-to-end testing of the Multi-MCP system using Puppeteer MCP tools. All implementation details, test cases, validation criteria, and success metrics are defined to ensure thorough testing coverage and system reliability.*