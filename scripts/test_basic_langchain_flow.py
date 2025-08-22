#!/usr/bin/env python
"""
Basic test to verify the LangChain integration is working.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi_server.chat_handler import ChatCompletionHandler
from fastapi_server.models import ChatMessage, ChatCompletionRequest, MessageRole


async def test_basic_flow():
    """Test basic chat completion flow with new LangChain implementation."""
    
    print("\nTesting Basic LangChain Flow")
    print("="*40)
    
    # Create handler
    handler = ChatCompletionHandler()
    
    try:
        # Create a simple request
        request = ChatCompletionRequest(
            messages=[
                ChatMessage(
                    role=MessageRole.USER,
                    content="Hello, can you help me?"
                )
            ]
        )
        
        print("1. Sending test message...")
        response = await handler.process_chat_completion(request)
        
        if response and response.choices:
            print(f"2. Response received: {response.choices[0].message.content[:100]}...")
            print("✓ Basic flow working!")
            return True
        else:
            print("✗ No response received")
            return False
            
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import os
    
    # Check for API keys
    if not (os.getenv('OPENROUTER_API_KEY') or os.getenv('GEMINI_API_KEY')):
        print("Warning: No API keys set. Test may fail.")
        print("Set OPENROUTER_API_KEY or GEMINI_API_KEY to test.")
    
    success = asyncio.run(test_basic_flow())
    sys.exit(0 if success else 1)