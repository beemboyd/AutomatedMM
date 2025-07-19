#!/usr/bin/env python3
"""
Test script for MCP servers

This script demonstrates how to interact with the MCP servers
"""

import json
import asyncio
from datetime import datetime, timedelta

async def test_portfolio_server():
    """Test portfolio MCP server queries"""
    print("=== Testing Portfolio MCP Server ===\n")
    
    # Example queries
    queries = [
        {
            "name": "Get portfolio metrics for the week",
            "tool": "get_portfolio_metrics",
            "arguments": {
                "period": "week"
            }
        },
        {
            "name": "Get top gainers",
            "tool": "get_top_transactions",
            "arguments": {
                "count": 5,
                "type": "gainers",
                "period": "week"
            }
        },
        {
            "name": "Analyze transactions summary",
            "tool": "analyze_transactions",
            "arguments": {
                "analysis_type": "summary",
                "start_date": "2025-05-19",
                "end_date": "2025-07-19"
            }
        }
    ]
    
    for query in queries:
        print(f"Query: {query['name']}")
        print(f"Tool: {query['tool']}")
        print(f"Arguments: {json.dumps(query['arguments'], indent=2)}")
        print("-" * 50)
        print()

async def test_market_server():
    """Test market MCP server queries"""
    print("\n=== Testing Market MCP Server ===\n")
    
    # Example queries
    queries = [
        {
            "name": "Get current market regime",
            "tool": "get_market_regime",
            "arguments": {
                "include_history": False
            }
        },
        {
            "name": "Analyze market breadth today",
            "tool": "analyze_market_breadth",
            "arguments": {
                "period": "today"
            }
        },
        {
            "name": "Get reversal analysis",
            "tool": "get_reversal_analysis",
            "arguments": {
                "type": "both",
                "include_tickers": False
            }
        },
        {
            "name": "Get trading insights",
            "tool": "get_market_insights",
            "arguments": {
                "focus": "trading"
            }
        },
        {
            "name": "Get index performance",
            "tool": "get_index_performance",
            "arguments": {
                "indices": ["NIFTY 50", "NIFTY MIDCAP 100"]
            }
        }
    ]
    
    for query in queries:
        print(f"Query: {query['name']}")
        print(f"Tool: {query['tool']}")
        print(f"Arguments: {json.dumps(query['arguments'], indent=2)}")
        print("-" * 50)
        print()

async def main():
    """Run all tests"""
    print("MCP Server Test Examples")
    print("=" * 60)
    print()
    
    await test_portfolio_server()
    await test_market_server()
    
    print("\nTo run these servers:")
    print("1. Portfolio Server: python portfolio_mcp_server.py")
    print("2. Market Server: python market_mcp_server.py")
    print()
    print("These servers implement the MCP protocol and can be integrated")
    print("with Claude or other MCP-compatible clients.")

if __name__ == "__main__":
    asyncio.run(main())