#!/usr/bin/env python3
"""
Simplified Portfolio MCP Server using the latest MCP API
"""

import asyncio
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Create a server instance
server = Server("portfolio-analysis")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """List available resources"""
    return [
        types.Resource(
            uri="portfolio://test",
            name="Test Resource",
            description="A test resource to verify the server works",
            mimeType="text/plain"
        )
    ]

@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read a specific resource"""
    if uri == "portfolio://test":
        return "Hello from Portfolio MCP Server!"
    return "Resource not found"

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="get_portfolio_summary",
            description="Get a summary of portfolio performance",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to analyze",
                        "default": 7
                    }
                }
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls"""
    if name == "get_portfolio_summary":
        days = arguments.get("days", 7)
        result = {
            "status": "success",
            "message": f"Portfolio summary for the last {days} days",
            "data": {
                "total_trades": 42,
                "winning_trades": 28,
                "losing_trades": 14,
                "win_rate": 66.67,
                "total_pnl": 15000.50
            }
        }
        return [types.TextContent(
            type="text",
            text=str(result)
        )]
    
    return [types.TextContent(
        type="text", 
        text=f"Unknown tool: {name}"
    )]

async def run():
    """Run the MCP server"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="portfolio-analysis",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(run())