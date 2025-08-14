#!/usr/bin/env python3
"""
Integration test script for multi-LLM provider support.
Tests both OpenRouter and Google Gemini providers.
"""

import os
import sys
import asyncio
import logging
from typing import Dict, Any, Optional

# Add the parent directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi_server.config import FastAPIServerConfig
from fastapi_server.llm_manager import LLMManager
from fastapi_server.chat_handler import ChatCompletionHandler
from fastapi_server.models import ChatMessage, ChatCompletionRequest, MessageRole

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MultiLLMTester:
    """Test class for multi-LLM provider functionality."""
    
    def __init__(self):
        """Initialize the tester."""
        self.test_results = {}
        self.original_env = {}
    
    def backup_environment(self):
        """Backup current environment variables."""
        env_vars = [
            'LLM_PROVIDER', 'OPENROUTER_API_KEY', 'OPENROUTER_MODEL',
            'GEMINI_API_KEY', 'GEMINI_MODEL'
        ]
        for var in env_vars:
            self.original_env[var] = os.environ.get(var)
    
    def restore_environment(self):
        """Restore original environment variables."""
        for var, value in self.original_env.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]
    
    def set_provider_environment(self, provider: str, api_key: Optional[str] = None):
        """Set environment variables for a specific provider."""
        os.environ['LLM_PROVIDER'] = provider
        
        if provider == "openrouter":
            if api_key:
                os.environ['OPENROUTER_API_KEY'] = api_key
            os.environ['OPENROUTER_MODEL'] = 'qwen/qwen3-coder:free'
        elif provider == "gemini":
            if api_key:
                os.environ['GEMINI_API_KEY'] = api_key
            os.environ['GEMINI_MODEL'] = 'gemini-pro'
    
    async def test_llm_manager_initialization(self, provider: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Test LLM manager initialization for a provider."""
        logger.info(f"Testing {provider} LLM manager initialization...")
        
        result = {
            "provider": provider,
            "initialization": False,
            "model_name": None,
            "provider_info": None,
            "error": None
        }
        
        try:
            # Set environment for this provider
            self.set_provider_environment(provider, api_key)
            
            # Force reload of config
            import importlib
            from fastapi_server import config
            importlib.reload(config)
            
            # Test initialization
            from fastapi_server.llm_manager import LLMManager
            manager = LLMManager()
            
            result["initialization"] = True
            result["model_name"] = manager._get_model_name()
            result["provider_info"] = manager.get_provider_info()
            
            logger.info(f"✓ {provider} manager initialized successfully")
            logger.info(f"  Model: {result['model_name']}")
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"✗ {provider} manager initialization failed: {e}")
        
        return result
    
    async def test_chat_completion(self, provider: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Test chat completion for a provider."""
        logger.info(f"Testing {provider} chat completion...")
        
        result = {
            "provider": provider,
            "chat_completion": False,
            "response_content": None,
            "response_length": 0,
            "has_usage": False,
            "error": None
        }
        
        if not api_key:
            result["error"] = "No API key provided for testing"
            logger.warning(f"⚠ {provider} chat completion skipped: No API key")
            return result
        
        try:
            # Set environment for this provider
            self.set_provider_environment(provider, api_key)
            
            # Force reload of config and reinitialize manager
            import importlib
            from fastapi_server import config, llm_manager
            importlib.reload(config)
            importlib.reload(llm_manager)
            
            from fastapi_server.llm_manager import LLMManager
            manager = LLMManager()
            
            # Test basic chat completion
            messages = [
                ChatMessage(
                    role=MessageRole.USER,
                    content="Hello! Please respond with a short greeting."
                )
            ]
            
            response = await manager.create_chat_completion(messages)
            
            result["chat_completion"] = True
            result["response_content"] = response.choices[0].message.content
            result["response_length"] = len(response.choices[0].message.content)
            result["has_usage"] = response.usage is not None
            
            logger.info(f"✓ {provider} chat completion successful")
            logger.info(f"  Response: {result['response_content'][:100]}...")
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"✗ {provider} chat completion failed: {e}")
        
        return result
    
    async def test_connection(self, provider: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Test connection to a provider."""
        logger.info(f"Testing {provider} connection...")
        
        result = {
            "provider": provider,
            "connection": False,
            "error": None
        }
        
        if not api_key:
            result["error"] = "No API key provided for testing"
            logger.warning(f"⚠ {provider} connection test skipped: No API key")
            return result
        
        try:
            # Set environment for this provider
            self.set_provider_environment(provider, api_key)
            
            # Force reload and reinitialize
            import importlib
            from fastapi_server import config, llm_manager
            importlib.reload(config)
            importlib.reload(llm_manager)
            
            from fastapi_server.llm_manager import LLMManager
            manager = LLMManager()
            
            # Test connection
            connection_result = await manager.test_connection()
            result["connection"] = connection_result
            
            if connection_result:
                logger.info(f"✓ {provider} connection successful")
            else:
                logger.error(f"✗ {provider} connection failed")
                
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"✗ {provider} connection test failed: {e}")
        
        return result
    
    async def test_full_integration(self, provider: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Test full integration with chat handler."""
        logger.info(f"Testing {provider} full integration...")
        
        result = {
            "provider": provider,
            "integration": False,
            "response_content": None,
            "error": None
        }
        
        if not api_key:
            result["error"] = "No API key provided for testing"
            logger.warning(f"⚠ {provider} integration test skipped: No API key")
            return result
        
        try:
            # Set environment for this provider
            self.set_provider_environment(provider, api_key)
            
            # Force reload of all modules
            import importlib
            from fastapi_server import config, llm_manager, chat_handler
            importlib.reload(config)
            importlib.reload(llm_manager)
            importlib.reload(chat_handler)
            
            # Test with chat handler
            from fastapi_server.chat_handler import ChatCompletionHandler
            handler = ChatCompletionHandler()
            
            request = ChatCompletionRequest(
                messages=[
                    ChatMessage(
                        role=MessageRole.USER,
                        content="What is 2 + 2? Please provide a brief answer."
                    )
                ]
            )
            
            response = await handler.process_chat_completion(request)
            
            result["integration"] = True
            result["response_content"] = response.choices[0].message.content
            
            logger.info(f"✓ {provider} full integration successful")
            logger.info(f"  Response: {result['response_content'][:100]}...")
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"✗ {provider} full integration failed: {e}")
        
        return result
    
    async def run_provider_tests(self, provider: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Run all tests for a specific provider."""
        logger.info(f"\n{'='*50}")
        logger.info(f"Testing {provider.upper()} Provider")
        logger.info(f"{'='*50}")
        
        results = {
            "provider": provider,
            "initialization": await self.test_llm_manager_initialization(provider, api_key),
            "connection": await self.test_connection(provider, api_key),
            "chat_completion": await self.test_chat_completion(provider, api_key),
            "integration": await self.test_full_integration(provider, api_key)
        }
        
        # Summary
        passed_tests = sum(1 for test in results.values() if isinstance(test, dict) and 
                          (test.get("initialization") or test.get("connection") or 
                           test.get("chat_completion") or test.get("integration")))
        
        logger.info(f"\n{provider.upper()} Summary: {passed_tests}/4 tests passed")
        
        return results
    
    async def run_all_tests(self):
        """Run tests for all supported providers."""
        logger.info("Starting Multi-LLM Provider Integration Tests")
        logger.info("=" * 60)
        
        # Backup original environment
        self.backup_environment()
        
        try:
            # Get API keys from environment
            openrouter_key = os.environ.get('OPENROUTER_API_KEY')
            gemini_key = os.environ.get('GEMINI_API_KEY')
            
            # Test OpenRouter
            openrouter_results = await self.run_provider_tests('openrouter', openrouter_key)
            self.test_results['openrouter'] = openrouter_results
            
            # Test Gemini
            gemini_results = await self.run_provider_tests('gemini', gemini_key)
            self.test_results['gemini'] = gemini_results
            
            # Overall summary
            self.print_final_summary()
            
        finally:
            # Restore original environment
            self.restore_environment()
    
    def print_final_summary(self):
        """Print final test summary."""
        logger.info("\n" + "=" * 60)
        logger.info("FINAL TEST SUMMARY")
        logger.info("=" * 60)
        
        for provider, results in self.test_results.items():
            logger.info(f"\n{provider.upper()} Provider:")
            
            for test_name, test_result in results.items():
                if test_name == "provider":
                    continue
                
                if isinstance(test_result, dict):
                    success = any(
                        test_result.get(key, False) for key in 
                        ["initialization", "connection", "chat_completion", "integration"]
                    )
                    status = "✓ PASS" if success else "✗ FAIL"
                    logger.info(f"  {test_name.replace('_', ' ').title()}: {status}")
                    
                    if test_result.get("error"):
                        logger.info(f"    Error: {test_result['error'][:100]}...")
        
        # Count overall results
        total_providers = len(self.test_results)
        working_providers = sum(
            1 for results in self.test_results.values()
            if any(
                test_result.get(key, False) for test_result in results.values()
                if isinstance(test_result, dict)
                for key in ["initialization", "connection", "chat_completion", "integration"]
            )
        )
        
        logger.info(f"\nOverall: {working_providers}/{total_providers} providers working")
        
        if working_providers == total_providers:
            logger.info("🎉 All providers are working correctly!")
        elif working_providers > 0:
            logger.info("⚠️  Some providers are working, check configurations for others.")
        else:
            logger.info("❌ No providers are working, check configurations and API keys.")


async def main():
    """Main test function."""
    try:
        tester = MultiLLMTester()
        await tester.run_all_tests()
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)