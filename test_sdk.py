#!/usr/bin/env python3
"""Test the claude_code_sdk directly."""

import asyncio
import logging
from claude_code_sdk import query, ClaudeCodeOptions, AssistantMessage, TextBlock, SystemMessage

logging.basicConfig(level=logging.DEBUG)

async def test_query():
    """Test basic query functionality."""
    print("Testing claude_code_sdk query...")
    
    message_count = 0
    response_text = ""
    
    try:
        async for message in query(
            prompt="Say hello and tell me what 2+2 equals",
            options=ClaudeCodeOptions(max_turns=1)
        ):
            message_count += 1
            print(f"\nMessage #{message_count}:")
            print(f"Type: {type(message).__name__}")
            print(f"Content: {str(message)[:200]}...")
            
            if isinstance(message, SystemMessage):
                print("  -> SystemMessage (skipping)")
            elif isinstance(message, AssistantMessage):
                print(f"  -> AssistantMessage with {len(message.content)} blocks")
                for i, block in enumerate(message.content):
                    print(f"     Block {i}: {type(block).__name__}")
                    if isinstance(block, TextBlock):
                        print(f"     Text: {block.text[:100]}...")
                        response_text += block.text
            else:
                print(f"  -> Unknown type: {message}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nTotal messages: {message_count}")
    print(f"Response text: {response_text}")

if __name__ == "__main__":
    asyncio.run(test_query())