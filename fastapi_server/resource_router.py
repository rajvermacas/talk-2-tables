"""
Dynamic resource router for intelligent MCP server selection.

This module uses LLM and intent classification to dynamically route
queries to the most appropriate MCP servers based on their capabilities.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import json

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel

from .intent_classifier import IntentClassification, QueryIntent

logger = logging.getLogger(__name__)


@dataclass
class ServerScore:
    """Score and reasoning for a server's relevance to a query."""
    server_name: str
    score: float
    reasoning: str
    capabilities_matched: List[str] = field(default_factory=list)
    resources_available: List[str] = field(default_factory=list)


@dataclass
class RoutingDecision:
    """Decision about which servers to use for a query."""
    primary_servers: List[str]
    secondary_servers: List[str] = field(default_factory=list)
    server_scores: Dict[str, ServerScore] = field(default_factory=dict)
    routing_strategy: str = ""
    fallback_strategy: str = ""
    confidence: float = 0.0


class ResourceRouter:
    """Routes queries to appropriate MCP servers based on intelligent analysis."""
    
    def __init__(self, llm: Optional[BaseChatModel] = None):
        """
        Initialize resource router.
        
        Args:
            llm: LangChain LLM instance for routing decisions
        """
        self.llm = llm
        self._routing_cache: Dict[str, RoutingDecision] = {}
        logger.info("Initialized resource router")
    
    async def route_query(
        self,
        query: str,
        intent: IntentClassification,
        available_servers: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> RoutingDecision:
        """
        Determine which MCP servers should handle a query.
        
        Args:
            query: User's natural language query
            intent: Classification of query intent
            available_servers: Information about available MCP servers
            context: Additional context
            
        Returns:
            RoutingDecision with server selection and strategy
        """
        
        # Use LLM for routing if available
        if self.llm:
            decision = await self._route_with_llm(
                query, intent, available_servers, context
            )
        else:
            # Fallback to intent-based routing
            decision = self._route_with_intent(
                intent, available_servers
            )
        
        logger.info(
            f"Routed query to servers: {decision.primary_servers} "
            f"(confidence: {decision.confidence:.2f})"
        )
        
        return decision
    
    async def _route_with_llm(
        self,
        query: str,
        intent: IntentClassification,
        available_servers: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> RoutingDecision:
        """Use LLM to make intelligent routing decisions."""
        
        # Build routing prompt
        system_prompt = self._build_routing_prompt()
        
        # Format server information
        servers_info = self._format_servers_info(available_servers)
        
        # Format intent information
        intent_info = f"""
Intent Classification:
- Primary Intent: {intent.primary_intent.value}
- Secondary Intents: {[i.value for i in intent.secondary_intents]}
- Required Resources: {list(intent.required_resources)}
- Entities Detected: {intent.entities_detected}
- Needs Database: {intent.needs_database}
- Needs Product Metadata: {intent.needs_product_metadata}
"""
        
        user_prompt = f"""Given this query and intent classification, determine which MCP servers should handle it:

Query: {query}

{intent_info}

Available MCP Servers:
{servers_info}

Provide a JSON response with:
{{
    "primary_servers": ["list of server names that MUST handle this query"],
    "secondary_servers": ["list of backup/supplementary servers"],
    "server_scores": {{
        "server_name": {{
            "score": 0.0-1.0,
            "reasoning": "why this server is relevant",
            "capabilities_matched": ["list of matched capabilities"],
            "resources_available": ["list of relevant resources"]
        }}
    }},
    "routing_strategy": "description of how to use the servers",
    "fallback_strategy": "what to do if primary servers fail",
    "confidence": 0.0-1.0
}}"""

        try:
            # Get LLM response
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Parse JSON response
            response_text = response.content
            
            # Extract JSON from response
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            # Parse the JSON
            result = json.loads(response_text)
            
            # Convert server scores
            server_scores = {}
            for server_name, score_data in result.get("server_scores", {}).items():
                server_scores[server_name] = ServerScore(
                    server_name=server_name,
                    score=float(score_data.get("score", 0.0)),
                    reasoning=score_data.get("reasoning", ""),
                    capabilities_matched=score_data.get("capabilities_matched", []),
                    resources_available=score_data.get("resources_available", [])
                )
            
            # Create routing decision
            decision = RoutingDecision(
                primary_servers=result.get("primary_servers", []),
                secondary_servers=result.get("secondary_servers", []),
                server_scores=server_scores,
                routing_strategy=result.get("routing_strategy", ""),
                fallback_strategy=result.get("fallback_strategy", ""),
                confidence=float(result.get("confidence", 0.8))
            )
            
            return decision
            
        except Exception as e:
            logger.error(f"LLM routing failed: {e}, falling back to intent-based routing")
            return self._route_with_intent(intent, available_servers)
    
    def _route_with_intent(
        self,
        intent: IntentClassification,
        available_servers: Dict[str, Any]
    ) -> RoutingDecision:
        """Fallback routing based on intent classification."""
        
        decision = RoutingDecision(
            primary_servers=[],
            routing_strategy="Intent-based routing",
            confidence=0.6
        )
        
        # Score each server based on intent needs
        for server_name, server_info in available_servers.items():
            if not isinstance(server_info, dict):
                continue
            
            score = 0.0
            capabilities_matched = []
            resources_available = []
            
            # Get server metadata
            domains = server_info.get("domains", [])
            capabilities = server_info.get("capabilities", [])
            resources = server_info.get("resources", {})
            priority = server_info.get("priority", 999)
            
            # Score based on intent needs
            if intent.needs_database and "database" in domains:
                score += 0.4
                capabilities_matched.append("database")
                if "database_metadata" in resources:
                    resources_available.append("database_metadata")
            
            if intent.needs_product_metadata and "products" in domains:
                score += 0.4
                capabilities_matched.append("products")
                if "product_aliases" in resources:
                    resources_available.append("product_aliases")
            
            if intent.needs_column_mappings and "metadata" in domains:
                score += 0.2
                capabilities_matched.append("metadata")
                if "column_mappings" in resources:
                    resources_available.append("column_mappings")
            
            # Bonus for suggested servers
            if server_name in intent.suggested_servers:
                score += 0.2
            
            # Adjust score based on priority (lower is better)
            score *= (1.0 / (1 + priority / 100))
            
            # Create server score
            if score > 0:
                decision.server_scores[server_name] = ServerScore(
                    server_name=server_name,
                    score=score,
                    reasoning=f"Matched {len(capabilities_matched)} capabilities",
                    capabilities_matched=capabilities_matched,
                    resources_available=resources_available
                )
        
        # Select primary servers (score > 0.3)
        ranked_servers = sorted(
            decision.server_scores.items(),
            key=lambda x: x[1].score,
            reverse=True
        )
        
        for server_name, server_score in ranked_servers:
            if server_score.score > 0.3:
                decision.primary_servers.append(server_name)
            elif server_score.score > 0.1:
                decision.secondary_servers.append(server_name)
        
        # Set fallback strategy
        if not decision.primary_servers:
            # No good match, use all available servers
            decision.primary_servers = list(available_servers.keys())
            decision.fallback_strategy = "No specific match, querying all servers"
            decision.confidence = 0.3
        else:
            decision.fallback_strategy = "Use secondary servers if primary fail"
        
        return decision
    
    def _build_routing_prompt(self) -> str:
        """Build the system prompt for LLM routing."""
        
        return """You are an intelligent query router for a multi-MCP system.
Your task is to analyze queries and their intent to determine which MCP servers should handle them.

Consider:
1. The query's intent and what resources it needs
2. Each server's capabilities and available resources
3. Server priorities (lower number = higher priority)
4. Efficiency - don't query servers unnecessarily

Routing strategies:
- Single server: When one server has everything needed
- Primary + fallback: When one server is best but others could help
- Parallel: When multiple servers have complementary data
- Sequential: When results from one server inform queries to another

Always prefer servers with:
- Lower priority numbers (they're preferred)
- Exact capability matches
- All required resources available

Provide clear reasoning for your routing decisions."""
    
    def _format_servers_info(self, available_servers: Dict[str, Any]) -> str:
        """Format server information for LLM prompt."""
        
        lines = []
        for server_name, server_info in available_servers.items():
            if isinstance(server_info, dict):
                lines.append(f"\n{server_name}:")
                lines.append(f"  Priority: {server_info.get('priority', 999)}")
                lines.append(f"  Domains: {', '.join(server_info.get('domains', []))}")
                lines.append(f"  Capabilities: {', '.join(server_info.get('capabilities', []))}")
                
                resources = server_info.get('resources', {})
                if resources:
                    resource_names = list(resources.keys())[:5]  # Limit to first 5
                    lines.append(f"  Resources: {', '.join(resource_names)}")
        
        return "\n".join(lines)
    
    async def rank_servers(
        self,
        servers: List[str],
        query: str,
        intent: IntentClassification,
        available_servers: Dict[str, Any]
    ) -> List[Tuple[str, float]]:
        """
        Rank servers by relevance to a query.
        
        Args:
            servers: List of server names to rank
            query: User query
            intent: Query intent classification
            available_servers: Server information
            
        Returns:
            List of (server_name, score) tuples, sorted by score
        """
        
        # Get routing decision
        decision = await self.route_query(query, intent, available_servers)
        
        # Extract scores
        ranked = []
        for server in servers:
            if server in decision.server_scores:
                score = decision.server_scores[server].score
            else:
                score = 0.0
            ranked.append((server, score))
        
        # Sort by score (highest first)
        ranked.sort(key=lambda x: x[1], reverse=True)
        
        return ranked
    
    def clear_cache(self):
        """Clear the routing cache."""
        self._routing_cache.clear()
        logger.info("Cleared routing cache")