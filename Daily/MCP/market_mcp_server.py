#!/usr/bin/env python3
"""
Market Conditions MCP Server

This MCP server provides access to market analysis data including:
- Market regime analysis and predictions
- Market breadth indicators
- Pattern analysis (G-patterns)
- Reversal counts and trends
- Index performance vs SMA
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp import Resource, Tool
from mcp.types import TextContent, ImageContent, EmbeddedResource
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

class MarketMCPServer:
    def __init__(self):
        self.server = Server("market-analysis")
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.regime_path = self.base_path / "Market_Regime"
        self.analysis_path = self.base_path / "Detailed_Analysis"
        self.g_pattern_path = self.base_path / "G_Pattern_Master"
        
        # Setup handlers
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup all MCP handlers"""
        
        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """List available resources"""
            resources = []
            
            # Market regime resources
            resources.append(Resource(
                uri="market://regime/latest",
                name="Latest Market Regime",
                description="Current market regime analysis and predictions",
                mimeType="application/json"
            ))
            
            resources.append(Resource(
                uri="market://regime/history",
                name="Regime History",
                description="Historical market regime transitions",
                mimeType="application/json"
            ))
            
            resources.append(Resource(
                uri="market://breadth/latest",
                name="Latest Market Breadth",
                description="Current market breadth indicators",
                mimeType="application/json"
            ))
            
            resources.append(Resource(
                uri="market://patterns/g-pattern",
                name="G-Pattern Analysis",
                description="G-Pattern history and current patterns",
                mimeType="application/json"
            ))
            
            return resources
        
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read a specific resource"""
            
            if uri == "market://regime/latest":
                filepath = self.regime_path / "regime_analysis" / "latest_regime_summary.json"
                if filepath.exists():
                    with open(filepath, 'r') as f:
                        return f.read()
            
            elif uri == "market://regime/history":
                filepath = self.regime_path / "data" / "regime_history.json"
                if filepath.exists():
                    with open(filepath, 'r') as f:
                        return f.read()
            
            elif uri == "market://breadth/latest":
                # Get the latest breadth file
                breadth_path = self.regime_path / "breadth_data"
                if breadth_path.exists():
                    breadth_files = list(breadth_path.glob("market_breadth_*.json"))
                    if breadth_files:
                        latest_file = max(breadth_files, key=lambda x: x.stat().st_mtime)
                        with open(latest_file, 'r') as f:
                            return f.read()
            
            elif uri == "market://patterns/g-pattern":
                filepath = self.g_pattern_path / "G_Pattern_History.json"
                if filepath.exists():
                    with open(filepath, 'r') as f:
                        return f.read()
            
            return json.dumps({"error": "Resource not found"})
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="get_market_regime",
                    description="Get current market regime analysis and recommendations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "include_history": {"type": "boolean", "default": False},
                            "history_days": {"type": "integer", "default": 7}
                        }
                    }
                ),
                Tool(
                    name="analyze_market_breadth",
                    description="Analyze market breadth indicators over time",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "period": {
                                "type": "string",
                                "enum": ["today", "3days", "week", "month"],
                                "default": "today"
                            },
                            "metrics": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Specific metrics to analyze"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_reversal_analysis",
                    description="Get analysis of long/short reversal patterns",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["long", "short", "both"],
                                "default": "both"
                            },
                            "include_tickers": {"type": "boolean", "default": False}
                        }
                    }
                ),
                Tool(
                    name="get_pattern_analysis",
                    description="Analyze G-patterns and other technical patterns",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pattern_type": {
                                "type": "string",
                                "enum": ["g-pattern", "kc-limits", "all"],
                                "default": "all"
                            },
                            "days": {"type": "integer", "default": 7}
                        }
                    }
                ),
                Tool(
                    name="get_index_performance",
                    description="Get index performance vs SMA analysis",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "indices": {
                                "type": "array",
                                "items": {"type": "string"},
                                "default": ["NIFTY 50", "NIFTY MIDCAP 100", "NIFTY SMLCAP 100"]
                            }
                        }
                    }
                ),
                Tool(
                    name="get_market_insights",
                    description="Get AI-generated market insights and recommendations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "focus": {
                                "type": "string",
                                "enum": ["trading", "risk", "opportunities", "all"],
                                "default": "all"
                            }
                        }
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> List[types.TextContent]:
            """Handle tool calls"""
            
            tool_handlers = {
                "get_market_regime": self.get_market_regime,
                "analyze_market_breadth": self.analyze_market_breadth,
                "get_reversal_analysis": self.get_reversal_analysis,
                "get_pattern_analysis": self.get_pattern_analysis,
                "get_index_performance": self.get_index_performance,
                "get_market_insights": self.get_market_insights
            }
            
            handler = tool_handlers.get(name)
            if handler:
                result = await handler(arguments or {})
            else:
                result = {"error": f"Unknown tool: {name}"}
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str)
            )]
    
    async def get_market_regime(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get current market regime analysis"""
        try:
            # Load latest regime summary
            summary_path = self.regime_path / "regime_analysis" / "latest_regime_summary.json"
            if not summary_path.exists():
                return {"error": "No regime data found"}
            
            with open(summary_path, 'r') as f:
                latest_regime = json.load(f)
            
            result = {
                "current_regime": latest_regime.get("market_regime"),
                "reversal_counts": latest_regime.get("reversal_counts"),
                "trend_analysis": latest_regime.get("trend_analysis"),
                "momentum_analysis": latest_regime.get("momentum_analysis"),
                "volatility": latest_regime.get("volatility"),
                "position_recommendations": latest_regime.get("position_recommendations"),
                "timestamp": latest_regime.get("timestamp")
            }
            
            # Include history if requested
            if args.get("include_history", False):
                history_path = self.regime_path / "data" / "regime_history.json"
                if history_path.exists():
                    with open(history_path, 'r') as f:
                        history_data = json.load(f)
                    
                    # Get last N days of history
                    days = args.get("history_days", 7)
                    cutoff = datetime.now() - timedelta(days=days)
                    
                    recent_history = []
                    for entry in history_data.get("history", [])[-100:]:  # Last 100 entries
                        try:
                            entry_time = datetime.fromisoformat(entry.get("timestamp", "").replace("Z", "+00:00"))
                            if entry_time >= cutoff:
                                recent_history.append(entry)
                        except:
                            continue
                    
                    result["regime_history"] = recent_history
                    
                    # Calculate regime distribution
                    regime_counts = defaultdict(int)
                    for entry in recent_history:
                        regime_counts[entry.get("regime", "unknown")] += 1
                    
                    total = sum(regime_counts.values())
                    if total > 0:
                        result["regime_distribution"] = {
                            regime: count/total for regime, count in regime_counts.items()
                        }
            
            return result
            
        except Exception as e:
            return {"error": str(e)}
    
    async def analyze_market_breadth(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze market breadth indicators"""
        try:
            period = args.get("period", "today")
            
            # Calculate date range
            end_date = datetime.now()
            if period == "today":
                start_date = end_date.replace(hour=0, minute=0, second=0)
            elif period == "3days":
                start_date = end_date - timedelta(days=3)
            elif period == "week":
                start_date = end_date - timedelta(days=7)
            else:  # month
                start_date = end_date - timedelta(days=30)
            
            # Load breadth data files
            breadth_path = self.regime_path / "breadth_data"
            if not breadth_path.exists():
                return {"error": "No breadth data found"}
            
            breadth_data = []
            for file in breadth_path.glob("market_breadth_*.json"):
                try:
                    # Extract date from filename
                    date_str = file.stem.split('_')[2]
                    file_date = datetime.strptime(date_str, '%Y%m%d')
                    
                    if start_date <= file_date <= end_date:
                        with open(file, 'r') as f:
                            data = json.load(f)
                            data['file_date'] = file_date.isoformat()
                            breadth_data.append(data)
                except:
                    continue
            
            if not breadth_data:
                return {"error": "No breadth data found for the specified period"}
            
            # Aggregate breadth metrics
            metrics = {
                "period": period,
                "data_points": len(breadth_data),
                "latest_reading": breadth_data[-1] if breadth_data else None,
                "averages": {},
                "trends": {}
            }
            
            # Calculate averages
            metric_names = [
                "advance_decline_ratio",
                "bullish_percent",
                "bearish_percent",
                "positive_momentum_percent",
                "strong_momentum_percent",
                "high_volume_percent"
            ]
            
            for metric in metric_names:
                values = []
                for data in breadth_data:
                    breadth = data.get("breadth_indicators", {})
                    if metric in breadth:
                        values.append(breadth[metric])
                
                if values:
                    metrics["averages"][metric] = {
                        "mean": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "latest": values[-1] if values else None
                    }
                    
                    # Calculate trend
                    if len(values) > 1:
                        trend = "increasing" if values[-1] > values[0] else "decreasing"
                        change = ((values[-1] - values[0]) / values[0] * 100) if values[0] != 0 else 0
                        metrics["trends"][metric] = {
                            "direction": trend,
                            "change_percent": change
                        }
            
            return metrics
            
        except Exception as e:
            return {"error": str(e)}
    
    async def get_reversal_analysis(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get analysis of reversal patterns"""
        try:
            reversal_type = args.get("type", "both")
            include_tickers = args.get("include_tickers", False)
            
            # Load latest regime summary for reversal counts
            summary_path = self.regime_path / "regime_analysis" / "latest_regime_summary.json"
            if not summary_path.exists():
                return {"error": "No regime data found"}
            
            with open(summary_path, 'r') as f:
                regime_data = json.load(f)
            
            result = {
                "reversal_counts": regime_data.get("reversal_counts", {}),
                "trend_analysis": regime_data.get("trend_analysis", {}),
                "momentum_analysis": regime_data.get("momentum_analysis", {}),
                "timestamp": regime_data.get("timestamp")
            }
            
            # Get actual reversal tickers if requested
            if include_tickers:
                scan_files = regime_data.get("scan_files", {})
                
                if reversal_type in ["long", "both"] and scan_files.get("long"):
                    try:
                        df = pd.read_excel(scan_files["long"])
                        result["long_reversals"] = {
                            "count": len(df),
                            "tickers": df['Ticker'].tolist() if 'Ticker' in df.columns else []
                        }
                    except:
                        pass
                
                if reversal_type in ["short", "both"] and scan_files.get("short"):
                    try:
                        df = pd.read_excel(scan_files["short"])
                        result["short_reversals"] = {
                            "count": len(df),
                            "tickers": df['Ticker'].tolist() if 'Ticker' in df.columns else []
                        }
                    except:
                        pass
            
            # Add insights
            long_count = result["reversal_counts"].get("long", 0)
            short_count = result["reversal_counts"].get("short", 0)
            
            if long_count > short_count * 1.5:
                result["market_bias"] = "Bullish - More long opportunities"
            elif short_count > long_count * 1.5:
                result["market_bias"] = "Bearish - More short opportunities"
            else:
                result["market_bias"] = "Neutral - Balanced opportunities"
            
            return result
            
        except Exception as e:
            return {"error": str(e)}
    
    async def get_pattern_analysis(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze technical patterns"""
        try:
            pattern_type = args.get("pattern_type", "all")
            days = args.get("days", 7)
            
            result = {
                "period_days": days,
                "patterns": {}
            }
            
            # G-Pattern Analysis
            if pattern_type in ["g-pattern", "all"]:
                g_pattern_file = self.g_pattern_path / "G_Pattern_History.json"
                if g_pattern_file.exists():
                    with open(g_pattern_file, 'r') as f:
                        g_data = json.load(f)
                    
                    # Get recent patterns
                    cutoff = datetime.now() - timedelta(days=days)
                    recent_patterns = []
                    
                    for pattern in g_data.get("patterns", [])[-50:]:  # Last 50 patterns
                        try:
                            pattern_date = datetime.fromisoformat(pattern.get("date", ""))
                            if pattern_date >= cutoff:
                                recent_patterns.append(pattern)
                        except:
                            continue
                    
                    result["patterns"]["g_patterns"] = {
                        "count": len(recent_patterns),
                        "recent": recent_patterns[-5:] if recent_patterns else []
                    }
            
            # KC Limits Analysis
            if pattern_type in ["kc-limits", "all"]:
                kc_upper_files = list(self.analysis_path.glob("KC_Upper_Limit_Trending_*.html"))
                kc_lower_files = list(self.analysis_path.glob("KC_Lower_Limit_Trending_*.html"))
                
                cutoff = datetime.now() - timedelta(days=days)
                
                def count_recent_files(files):
                    count = 0
                    for file in files:
                        try:
                            date_str = file.stem.split('_')[-2]
                            file_date = datetime.strptime(date_str, '%Y%m%d')
                            if file_date >= cutoff:
                                count += 1
                        except:
                            continue
                    return count
                
                result["patterns"]["kc_limits"] = {
                    "upper_limit_signals": count_recent_files(kc_upper_files),
                    "lower_limit_signals": count_recent_files(kc_lower_files)
                }
            
            return result
            
        except Exception as e:
            return {"error": str(e)}
    
    async def get_index_performance(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get index performance vs SMA analysis"""
        try:
            indices = args.get("indices", ["NIFTY 50", "NIFTY MIDCAP 100", "NIFTY SMLCAP 100"])
            
            # Load latest regime summary for index data
            summary_path = self.regime_path / "regime_analysis" / "latest_regime_summary.json"
            if not summary_path.exists():
                return {"error": "No regime data found"}
            
            with open(summary_path, 'r') as f:
                regime_data = json.load(f)
            
            index_analysis = regime_data.get("index_analysis", {})
            index_details = index_analysis.get("index_details", {})
            
            result = {
                "overall_trend": index_analysis.get("trend"),
                "trend_strength": index_analysis.get("strength"),
                "indices_above_sma20": index_analysis.get("indices_above_sma20"),
                "total_indices": index_analysis.get("total_indices"),
                "analysis": index_analysis.get("analysis"),
                "indices": {}
            }
            
            # Add individual index details
            for index in indices:
                if index in index_details:
                    result["indices"][index] = index_details[index]
            
            # Add market interpretation
            above_sma = index_analysis.get("indices_above_sma20", 0)
            total = index_analysis.get("total_indices", 3)
            
            if above_sma == total:
                result["market_state"] = "Strong Bullish - All indices above SMA20"
            elif above_sma >= total * 0.66:
                result["market_state"] = "Bullish - Majority indices above SMA20"
            elif above_sma >= total * 0.33:
                result["market_state"] = "Neutral - Mixed index performance"
            else:
                result["market_state"] = "Bearish - Most indices below SMA20"
            
            return result
            
        except Exception as e:
            return {"error": str(e)}
    
    async def get_market_insights(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI-generated market insights"""
        try:
            focus = args.get("focus", "all")
            
            # Load latest regime summary
            summary_path = self.regime_path / "regime_analysis" / "latest_regime_summary.json"
            if not summary_path.exists():
                return {"error": "No regime data found"}
            
            with open(summary_path, 'r') as f:
                regime_data = json.load(f)
            
            insights = {
                "timestamp": regime_data.get("timestamp"),
                "market_regime": regime_data.get("market_regime", {}).get("regime"),
                "insights": []
            }
            
            # Get existing insights
            if "insights" in regime_data:
                insights["insights"] = regime_data["insights"]
            
            # Add focused insights based on request
            if focus in ["trading", "all"]:
                position_rec = regime_data.get("position_recommendations", {})
                insights["trading_recommendations"] = {
                    "preferred_direction": position_rec.get("preferred_direction"),
                    "position_size_multiplier": position_rec.get("position_size_multiplier"),
                    "max_positions": position_rec.get("max_positions"),
                    "entry_strategy": position_rec.get("entry_strategy"),
                    "exit_strategy": position_rec.get("exit_strategy"),
                    "avoid": position_rec.get("avoid")
                }
            
            if focus in ["risk", "all"]:
                volatility = regime_data.get("volatility", {})
                insights["risk_analysis"] = {
                    "volatility_regime": volatility.get("volatility_regime"),
                    "volatility_score": volatility.get("volatility_score"),
                    "stop_loss_multiplier": regime_data.get("position_recommendations", {}).get("stop_loss_multiplier"),
                    "risk_per_trade": regime_data.get("position_recommendations", {}).get("risk_per_trade"),
                    "guidance": regime_data.get("position_recommendations", {}).get("specific_guidance", [])
                }
            
            if focus in ["opportunities", "all"]:
                reversal_counts = regime_data.get("reversal_counts", {})
                insights["opportunities"] = {
                    "long_setups": reversal_counts.get("long", 0),
                    "short_setups": reversal_counts.get("short", 0),
                    "total_setups": reversal_counts.get("total", 0),
                    "market_bias": "Bullish" if reversal_counts.get("long", 0) > reversal_counts.get("short", 0) else "Bearish",
                    "confidence_level": regime_data.get("market_regime", {}).get("confidence_level")
                }
            
            return insights
            
        except Exception as e:
            return {"error": str(e)}
    
    async def run(self):
        """Run the MCP server"""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="market-analysis",
                    server_version="0.1.0",
                    capabilities=self.server.get_capabilities(),
                ),
            )

if __name__ == "__main__":
    server = MarketMCPServer()
    asyncio.run(server.run())