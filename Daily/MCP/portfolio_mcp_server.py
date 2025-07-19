#!/usr/bin/env python3
"""
Portfolio Performance MCP Server

This MCP server provides access to portfolio performance data including:
- Transaction analysis from Excel files
- Order history and success rates
- Position performance metrics
- User-wise performance tracking
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import local utilities
from utils import (
    read_transaction_excel, 
    parse_order_filename, 
    calculate_portfolio_metrics,
    aggregate_order_data,
    format_currency
)

from mcp.server import Server, NotificationOptions
from mcp import Resource, Tool
from mcp.types import TextContent, ImageContent, EmbeddedResource
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

class PortfolioMCPServer:
    def __init__(self):
        self.server = Server("portfolio-analysis")
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_path = self.base_path / "data"
        self.orders_path = self.base_path / "Current_Orders"
        self.transactions_path = self.data_path / "Transactions"
        
        # Setup handlers
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup all MCP handlers"""
        
        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """List available resources"""
            resources = []
            
            # Add transaction files
            if self.transactions_path.exists():
                transaction_files = sorted(self.transactions_path.glob("*.xlsx"), reverse=True)
                for file in transaction_files:
                    resources.append(Resource(
                        uri=f"portfolio://transactions/{file.name}",
                        name=f"Transactions: {file.stem}",
                        description=f"Transaction data from {file.name}",
                        mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    ))
            
            # Add order history
            if self.orders_path.exists():
                for user_dir in self.orders_path.iterdir():
                    if user_dir.is_dir():
                        resources.append(Resource(
                            uri=f"portfolio://orders/{user_dir.name}",
                            name=f"Orders: {user_dir.name}",
                            description=f"Order history for user {user_dir.name}",
                            mimeType="application/json"
                        ))
            
            return resources
        
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read a specific resource"""
            if uri.startswith("portfolio://transactions/"):
                filename = uri.replace("portfolio://transactions/", "")
                filepath = self.transactions_path / filename
                if filepath.exists():
                    df = pd.read_excel(filepath)
                    return df.to_json(orient='records', date_format='iso')
            
            elif uri.startswith("portfolio://orders/"):
                user = uri.replace("portfolio://orders/", "")
                user_path = self.orders_path / user
                if user_path.exists():
                    # Get latest order file
                    order_files = list(user_path.glob("orders_*.json"))
                    if order_files:
                        latest_file = max(order_files, key=lambda x: x.stat().st_mtime)
                        with open(latest_file, 'r') as f:
                            return f.read()
            
            return json.dumps({"error": "Resource not found"})
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="analyze_transactions",
                    description="Analyze transactions from Excel file for a date range",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "format": "date"},
                            "end_date": {"type": "string", "format": "date"},
                            "user": {"type": "string", "description": "Optional: Filter by user"},
                            "analysis_type": {
                                "type": "string",
                                "enum": ["summary", "top_gainers", "top_losers", "by_strategy", "by_user"],
                                "default": "summary"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_portfolio_metrics",
                    description="Get overall portfolio performance metrics",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "period": {
                                "type": "string",
                                "enum": ["today", "week", "month", "all"],
                                "default": "week"
                            },
                            "user": {"type": "string", "description": "Optional: Filter by user"}
                        }
                    }
                ),
                Tool(
                    name="analyze_order_performance",
                    description="Analyze order performance and success rates",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user": {"type": "string", "description": "User to analyze"},
                            "days": {"type": "integer", "default": 7}
                        },
                        "required": ["user"]
                    }
                ),
                Tool(
                    name="get_top_transactions",
                    description="Get top performing transactions",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "count": {"type": "integer", "default": 10},
                            "type": {
                                "type": "string",
                                "enum": ["gainers", "losers", "volume"],
                                "default": "gainers"
                            },
                            "period": {
                                "type": "string",
                                "enum": ["today", "week", "month"],
                                "default": "week"
                            }
                        }
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> List[types.TextContent]:
            """Handle tool calls"""
            
            if name == "analyze_transactions":
                result = await self.analyze_transactions(arguments or {})
            elif name == "get_portfolio_metrics":
                result = await self.get_portfolio_metrics(arguments or {})
            elif name == "analyze_order_performance":
                result = await self.analyze_order_performance(arguments or {})
            elif name == "get_top_transactions":
                result = await self.get_top_transactions(arguments or {})
            else:
                result = {"error": f"Unknown tool: {name}"}
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str)
            )]
    
    async def analyze_transactions(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze transactions from Excel files"""
        try:
            # Find the appropriate transaction file
            transaction_files = list(self.transactions_path.glob("*.xlsx"))
            if not transaction_files:
                return {"error": "No transaction files found"}
            
            # Sort files by name (assuming date format in filename) and use the most recent
            transaction_files.sort(reverse=True)
            selected_file = transaction_files[0]
            
            # If specific date range requested, try to find matching file
            if 'start_date' in args and 'end_date' in args:
                # Look for file that might match the date range
                for file in transaction_files:
                    # Check if filename contains date range (e.g., 06192025-07192025.xlsx)
                    if args['start_date'].replace('-', '') in file.name or args['end_date'].replace('-', '') in file.name:
                        selected_file = file
                        break
            
            print(f"Using transaction file: {selected_file.name}", file=sys.stderr)
            df = read_transaction_excel(selected_file)
            
            # Filter by user if specified
            if 'user' in args and args['user']:
                df = df[df['User'] == args['user']] if 'User' in df.columns else df
            
            analysis_type = args.get('analysis_type', 'summary')
            
            if analysis_type == 'summary':
                return {
                    "total_transactions": len(df),
                    "total_volume": float(df['Amount'].sum()) if 'Amount' in df.columns else 0,
                    "profitable_trades": len(df[df['PnL'] > 0]) if 'PnL' in df.columns else 0,
                    "loss_trades": len(df[df['PnL'] < 0]) if 'PnL' in df.columns else 0,
                    "total_pnl": float(df['PnL'].sum()) if 'PnL' in df.columns else 0,
                    "avg_pnl": float(df['PnL'].mean()) if 'PnL' in df.columns else 0,
                    "win_rate": (len(df[df['PnL'] > 0]) / len(df) * 100) if 'PnL' in df.columns and len(df) > 0 else 0
                }
            
            elif analysis_type == 'top_gainers':
                if 'PnL' in df.columns:
                    top = df.nlargest(10, 'PnL')[['Symbol', 'PnL', 'Date']].to_dict('records')
                    return {"top_gainers": top}
            
            elif analysis_type == 'top_losers':
                if 'PnL' in df.columns:
                    top = df.nsmallest(10, 'PnL')[['Symbol', 'PnL', 'Date']].to_dict('records')
                    return {"top_losers": top}
            
            elif analysis_type == 'by_strategy':
                if 'Strategy' in df.columns:
                    strategy_perf = df.groupby('Strategy').agg({
                        'PnL': ['sum', 'mean', 'count'],
                        'Symbol': 'count'
                    }).to_dict()
                    return {"strategy_performance": strategy_perf}
            
            elif analysis_type == 'by_user':
                if 'User' in df.columns:
                    user_perf = df.groupby('User').agg({
                        'PnL': ['sum', 'mean', 'count'],
                        'Amount': 'sum'
                    }).to_dict()
                    return {"user_performance": user_perf}
            
            return {"error": f"Unknown analysis type: {analysis_type}"}
            
        except Exception as e:
            return {"error": str(e)}
    
    async def get_portfolio_metrics(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get overall portfolio performance metrics"""
        try:
            period = args.get('period', 'week')
            user_filter = args.get('user')
            
            # Calculate date range based on period
            end_date = datetime.now()
            if period == 'today':
                start_date = end_date.replace(hour=0, minute=0, second=0)
            elif period == 'week':
                start_date = end_date - timedelta(days=7)
            elif period == 'month':
                start_date = end_date - timedelta(days=30)
            else:  # all
                start_date = datetime(2020, 1, 1)
            
            # Aggregate metrics from various sources
            metrics = {
                "period": period,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "metrics": {}
            }
            
            # Load transaction data
            transaction_files = list(self.transactions_path.glob("*.xlsx"))
            if transaction_files:
                df = pd.read_excel(transaction_files[0])
                
                if user_filter and 'User' in df.columns:
                    df = df[df['User'] == user_filter]
                
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'])
                    df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]
                
                if 'PnL' in df.columns:
                    metrics['metrics']['total_pnl'] = float(df['PnL'].sum())
                    metrics['metrics']['avg_pnl'] = float(df['PnL'].mean())
                    metrics['metrics']['max_gain'] = float(df['PnL'].max())
                    metrics['metrics']['max_loss'] = float(df['PnL'].min())
                    metrics['metrics']['win_rate'] = (len(df[df['PnL'] > 0]) / len(df) * 100) if len(df) > 0 else 0
                    metrics['metrics']['total_trades'] = len(df)
                    
                    # Calculate Sharpe ratio
                    if len(df) > 1:
                        returns = df['PnL'] / df['Amount'] if 'Amount' in df.columns else df['PnL']
                        sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
                        metrics['metrics']['sharpe_ratio'] = float(sharpe)
            
            return metrics
            
        except Exception as e:
            return {"error": str(e)}
    
    async def analyze_order_performance(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze order performance for a specific user"""
        try:
            user = args['user']
            days = args.get('days', 7)
            
            user_path = self.orders_path / user
            if not user_path.exists():
                return {"error": f"No order data found for user: {user}"}
            
            # Get order files from the last N days
            cutoff_date = datetime.now() - timedelta(days=days)
            order_data = []
            
            for order_file in user_path.glob("orders_*.json"):
                # Extract date from filename
                file_date_str = order_file.stem.split('_')[2]
                try:
                    file_date = datetime.strptime(file_date_str, '%Y%m%d')
                    if file_date >= cutoff_date:
                        with open(order_file, 'r') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                order_data.extend(data)
                            else:
                                order_data.append(data)
                except:
                    continue
            
            if not order_data:
                return {"error": "No orders found in the specified period"}
            
            # Analyze performance
            total_orders = len(order_data)
            successful = sum(1 for o in order_data if o.get('status') == 'success')
            failed = sum(1 for o in order_data if o.get('status') == 'failed')
            
            total_investment = sum(o.get('investment', 0) for o in order_data)
            total_pnl = sum(o.get('pnl', 0) for o in order_data)
            
            return {
                "user": user,
                "period_days": days,
                "total_orders": total_orders,
                "successful_orders": successful,
                "failed_orders": failed,
                "success_rate": (successful / total_orders * 100) if total_orders > 0 else 0,
                "total_investment": total_investment,
                "total_pnl": total_pnl,
                "roi": (total_pnl / total_investment * 100) if total_investment > 0 else 0,
                "avg_order_size": total_investment / total_orders if total_orders > 0 else 0
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def get_top_transactions(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get top performing transactions"""
        try:
            count = args.get('count', 10)
            trans_type = args.get('type', 'gainers')
            period = args.get('period', 'week')
            
            # Calculate date range
            end_date = datetime.now()
            if period == 'today':
                start_date = end_date.replace(hour=0, minute=0, second=0)
            elif period == 'week':
                start_date = end_date - timedelta(days=7)
            else:  # month
                start_date = end_date - timedelta(days=30)
            
            # Load transaction data
            transaction_files = list(self.transactions_path.glob("*.xlsx"))
            if not transaction_files:
                return {"error": "No transaction files found"}
            
            df = pd.read_excel(transaction_files[0])
            
            # Filter by date if Date column exists
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]
            
            result = {
                "period": period,
                "type": trans_type,
                "transactions": []
            }
            
            if trans_type == 'gainers' and 'PnL' in df.columns:
                top = df.nlargest(count, 'PnL')
            elif trans_type == 'losers' and 'PnL' in df.columns:
                top = df.nsmallest(count, 'PnL')
            elif trans_type == 'volume' and 'Amount' in df.columns:
                top = df.nlargest(count, 'Amount')
            else:
                return {"error": "Required columns not found in data"}
            
            # Convert to records
            cols_to_include = ['Symbol', 'PnL', 'Amount', 'Date', 'User', 'Strategy']
            cols_to_include = [c for c in cols_to_include if c in df.columns]
            
            result['transactions'] = top[cols_to_include].to_dict('records')
            
            return result
            
        except Exception as e:
            return {"error": str(e)}
    
    async def run(self):
        """Run the MCP server"""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="portfolio-analysis",
                    server_version="0.1.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

if __name__ == "__main__":
    server = PortfolioMCPServer()
    asyncio.run(server.run())