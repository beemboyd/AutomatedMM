#!/usr/bin/env python3
"""
Portfolio-Specific Market Regime Analysis
Analyzes your actual Zerodha portfolio positions and generates HTML report
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, List, Tuple

# Add paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ML.utils.market_regime import MarketRegimeDetector, MarketRegimeType

# Try to import Zerodha components
try:
    from zerodha_handler import ZerodhaHandler
    from config import Config
    HAS_ZERODHA = True
except ImportError:
    HAS_ZERODHA = False
    logging.warning("Zerodha modules not available. Using fallback data.")

# Try to import plotting libraries for HTML reports
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False
    logging.warning("Plotly not available. Charts will be excluded from HTML report.")

class PortfolioRegimeAnalyzer:
    def __init__(self):
        self.detector = MarketRegimeDetector()
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_dir = os.path.join(self.base_dir, 'BT', 'data')
        
    def load_portfolio_positions(self, use_zerodha=True):
        """Load current positions from Zerodha API or trading_state.json"""
        
        # Try Zerodha API first if available and requested
        if use_zerodha and HAS_ZERODHA:
            try:
                # Initialize KiteConnect directly (similar to SL_watchdog.py)
                from kiteconnect import KiteConnect
                
                # Load config
                config_path = os.path.join(self.base_dir, 'Daily', 'config.ini')
                if not os.path.exists(config_path):
                    config_path = os.path.join(self.base_dir, 'config.ini')
                
                import configparser
                config = configparser.ConfigParser()
                config.read(config_path)
                
                # Get credentials from DEFAULT user or first available user
                api_key = config.get('DEFAULT', 'api_key', fallback='')
                api_secret = config.get('DEFAULT', 'api_secret', fallback='')
                access_token = config.get('DEFAULT', 'access_token', fallback='')
                
                # If DEFAULT doesn't have credentials, try to find first user with access token
                if not all([api_key, api_secret, access_token]):
                    for section in config.sections():
                        if section.startswith('API_CREDENTIALS_'):
                            api_key = config.get(section, 'api_key', fallback='')
                            api_secret = config.get(section, 'api_secret', fallback='')
                            access_token = config.get(section, 'access_token', fallback='')
                            
                            # Use first credentials with valid access token
                            if all([api_key, api_secret, access_token]):
                                user_name = section.replace('API_CREDENTIALS_', '')
                                print(f"Using credentials for user: {user_name}")
                                break
                
                if not all([api_key, api_secret, access_token]):
                    raise ValueError("No valid Zerodha credentials found in config")
                
                # Initialize KiteConnect
                kite = KiteConnect(api_key=api_key)
                kite.set_access_token(access_token)
                
                # Verify connection
                profile = kite.profile()
                print(f"Connected to Zerodha account: {profile['user_name']} (ID: {profile['user_id']})")
                
                # Get positions and holdings (similar to SL_watchdog.py)
                positions_data = kite.positions()
                holdings_data = kite.holdings()
                
                portfolio = {}
                
                # Process net positions (CNC only)
                for position in positions_data.get('net', []):
                    ticker = position.get('tradingsymbol', '')
                    product = position.get('product', '')
                    quantity = int(position.get('quantity', 0))
                    
                    if product == 'CNC' and quantity > 0 and ticker:
                        portfolio[ticker] = {
                            'type': 'LONG',
                            'quantity': quantity,
                            'entry_price': float(position.get('average_price', 0)),
                            'product': product,
                            'exchange': position.get('exchange', 'NSE'),
                            'pnl': float(position.get('pnl', 0)),
                            'unrealised': float(position.get('unrealised', 0))
                        }
                
                # Process holdings (CNC positions carried overnight)
                existing_tickers = set(portfolio.keys())
                for holding in holdings_data:
                    ticker = holding.get('tradingsymbol', '')
                    quantity = int(holding.get('quantity', 0))
                    t1_quantity = int(holding.get('t1_quantity', 0))
                    total_quantity = quantity + t1_quantity
                    
                    if total_quantity > 0 and ticker and ticker not in existing_tickers:
                        portfolio[ticker] = {
                            'type': 'LONG',
                            'quantity': total_quantity,
                            'entry_price': float(holding.get('average_price', 0)),
                            'product': 'CNC',
                            'exchange': holding.get('exchange', 'NSE'),
                            'pnl': float(holding.get('pnl', 0)),
                            'settled_quantity': quantity,
                            't1_quantity': t1_quantity
                        }
                
                if portfolio:
                    print(f"Loaded {len(portfolio)} CNC positions from Zerodha API")
                    return portfolio
                else:
                    print("No CNC positions found in Zerodha account")
                    
            except Exception as e:
                logging.error(f"Failed to load positions from Zerodha: {e}")
                print(f"Failed to load from Zerodha API: {e}")
                print("Falling back to local state file...")
        
        # Fallback to trading_state.json
        state_path = os.path.join(self.base_dir, 'data', 'trading_state.json')
        
        if os.path.exists(state_path):
            with open(state_path, 'r') as f:
                state = json.load(f)
                positions = state.get('positions', {})
                if positions:
                    print(f"Loaded {len(positions)} positions from trading_state.json")
                    return positions
        
        # Final fallback to example portfolio
        print("No positions found. Using example portfolio for demonstration...")
        return {
            'RELIANCE': {'type': 'LONG', 'quantity': 100, 'entry_price': 1400},
            'TCS': {'type': 'LONG', 'quantity': 50, 'entry_price': 3500},
            'HDFCBANK': {'type': 'LONG', 'quantity': 75, 'entry_price': 1900}
        }
    
    def load_ticker_data(self, ticker):
        """Load historical data for a ticker"""
        file_path = os.path.join(self.data_dir, f'{ticker}_day.csv')
        
        if os.path.exists(file_path):
            data = pd.read_csv(file_path)
            data['date'] = pd.to_datetime(data['date'])
            data = data.set_index('date')
            
            # Use last 252 trading days
            if len(data) > 252:
                data = data.iloc[-252:]
            
            return data
        return None
    
    def analyze_position(self, ticker, position_info):
        """Analyze a single position"""
        data = self.load_ticker_data(ticker)
        
        if data is None:
            return {'ticker': ticker, 'error': 'No data available'}
        
        # Detect regime
        regime, metrics = self.detector.detect_consolidated_regime(data)
        
        # Get current values
        current_regime = regime.iloc[-1]
        current_price = data['Close'].iloc[-1]
        
        # Calculate metrics
        volatility = metrics['volatility'].iloc[-1] if 'volatility' in metrics else 0
        trend_strength = metrics['trend_strength'].iloc[-1] if 'trend_strength' in metrics else 0
        
        # Calculate ATR
        high = data['High']
        low = data['Low']
        close = data['Close']
        close_prev = close.shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close_prev)
        tr3 = abs(low - close_prev)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        # Determine action based on regime
        if current_regime == MarketRegimeType.TRENDING_BULLISH.value:
            if position_info['type'] == 'LONG':
                action = 'HOLD_OR_ADD'
                position_factor = 1.2
                stop_multiplier = 2.0
            else:
                action = 'CONSIDER_EXIT'
                position_factor = 0.5
                stop_multiplier = 1.2
        
        elif current_regime == MarketRegimeType.TRENDING_BEARISH.value:
            if position_info['type'] == 'LONG':
                action = 'REDUCE_OR_EXIT'
                position_factor = 0.4
                stop_multiplier = 1.0
            else:
                action = 'HOLD_OR_ADD'
                position_factor = 1.2
                stop_multiplier = 2.0
        
        elif current_regime == MarketRegimeType.RANGING_HIGH_VOL.value:
            action = 'REDUCE_SIZE'
            position_factor = 0.5
            stop_multiplier = 2.5
        
        else:  # RANGING_LOW_VOL or TRANSITIONING
            action = 'MONITOR'
            position_factor = 0.8
            stop_multiplier = 1.5
        
        # Calculate P&L
        entry_price = position_info.get('entry_price', current_price)
        quantity = position_info.get('quantity', 0)
        
        if position_info['type'] == 'LONG':
            pnl = (current_price - entry_price) * quantity
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            stop_loss = current_price - (atr * stop_multiplier)
        else:
            pnl = (entry_price - current_price) * quantity
            pnl_pct = ((entry_price - current_price) / entry_price) * 100
            stop_loss = current_price + (atr * stop_multiplier)
        
        return {
            'ticker': ticker,
            'position_type': position_info['type'],
            'entry_price': entry_price,
            'current_price': current_price,
            'quantity': quantity,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'regime': current_regime,
            'action': action,
            'volatility': volatility,
            'trend_strength': trend_strength,
            'atr': atr,
            'stop_loss': stop_loss,
            'stop_multiplier': stop_multiplier,
            'position_factor': position_factor
        }
    
    def generate_portfolio_report(self, use_zerodha=False):
        """Generate comprehensive portfolio analysis"""
        positions = self.load_portfolio_positions(use_zerodha=use_zerodha)
        
        if not positions:
            print("No positions found in portfolio!")
            return
        
        print("=" * 100)
        print(f"PORTFOLIO REGIME ANALYSIS - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 100)
        
        results = []
        total_value = 0
        total_pnl = 0
        
        # Analyze each position
        for ticker, position_info in positions.items():
            result = self.analyze_position(ticker, position_info)
            results.append(result)
            
            if 'error' not in result:
                position_value = result['current_price'] * result['quantity']
                total_value += position_value
                total_pnl += result['pnl']
        
        # Portfolio Summary
        print(f"\nPORTFOLIO SUMMARY:")
        print(f"Total Positions: {len(positions)}")
        print(f"Total Value: ₹{total_value:,.2f}")
        print(f"Total P&L: ₹{total_pnl:,.2f} ({(total_pnl/total_value)*100:.2f}%)")
        
        # Regime Distribution
        regime_counts = {}
        for result in results:
            if 'regime' in result:
                regime = result['regime']
                regime_counts[regime] = regime_counts.get(regime, 0) + 1
        
        print(f"\nREGIME DISTRIBUTION:")
        for regime, count in regime_counts.items():
            percentage = (count / len(positions)) * 100
            print(f"  {regime:25} | {count} positions ({percentage:.1f}%)")
        
        # Detailed Position Analysis
        print("\n" + "=" * 100)
        print("POSITION ANALYSIS:")
        print("=" * 100)
        
        # Sort by action priority
        action_priority = {
            'REDUCE_OR_EXIT': 1,
            'CONSIDER_EXIT': 2,
            'REDUCE_SIZE': 3,
            'MONITOR': 4,
            'HOLD_OR_ADD': 5
        }
        
        results_sorted = sorted(results, 
                              key=lambda x: action_priority.get(x.get('action', 'MONITOR'), 4))
        
        for result in results_sorted:
            if 'error' in result:
                print(f"\n{result['ticker']}: {result['error']}")
                continue
            
            # Header with P&L
            pnl_sign = '+' if result['pnl'] >= 0 else ''
            print(f"\n{result['ticker']} ({result['position_type']}):")
            print(f"  Entry: ₹{result['entry_price']:.2f} → Current: ₹{result['current_price']:.2f}")
            print(f"  P&L: {pnl_sign}₹{result['pnl']:,.2f} ({pnl_sign}{result['pnl_pct']:.2f}%)")
            print(f"  Quantity: {result['quantity']}")
            
            # Regime and Action
            print(f"\n  Regime: {result['regime']}")
            print(f"  ACTION: {result['action']}")
            
            # Risk Management
            print(f"\n  Stop Loss: ₹{result['stop_loss']:.2f} ({result['stop_multiplier']}x ATR)")
            stop_distance = abs(result['current_price'] - result['stop_loss'])
            stop_pct = (stop_distance / result['current_price']) * 100
            print(f"  Stop Distance: ₹{stop_distance:.2f} ({stop_pct:.1f}%)")
            
            # Position Sizing
            print(f"  Position Size Recommendation: {result['position_factor']*100:.0f}% of normal")
            
            # Special Warnings
            if result['action'] in ['REDUCE_OR_EXIT', 'CONSIDER_EXIT']:
                print(f"  ⚠️  WARNING: Regime not favorable for {result['position_type']} position")
            
            if result['volatility'] > 0.04:
                print(f"  ⚠️  HIGH VOLATILITY: {result['volatility']:.4f}")
        
        # Action Summary
        print("\n" + "=" * 100)
        print("ACTION SUMMARY:")
        print("=" * 100)
        
        actions_grouped = {}
        for result in results:
            if 'action' in result:
                action = result['action']
                if action not in actions_grouped:
                    actions_grouped[action] = []
                actions_grouped[action].append(result['ticker'])
        
        for action in sorted(actions_grouped.keys(), 
                           key=lambda x: action_priority.get(x, 4)):
            tickers = actions_grouped[action]
            print(f"\n{action}:")
            print(f"  {', '.join(tickers)}")
        
        # Risk Report
        print("\n" + "=" * 100)
        print("RISK MANAGEMENT CHECKLIST:")
        print("=" * 100)
        
        print("\n1. IMMEDIATE ACTIONS:")
        urgent_exits = [r['ticker'] for r in results 
                       if r.get('action') in ['REDUCE_OR_EXIT', 'CONSIDER_EXIT']]
        if urgent_exits:
            print(f"   - Review and potentially exit: {', '.join(urgent_exits)}")
        else:
            print("   - No urgent exits required")
        
        print("\n2. STOP LOSS UPDATES:")
        for result in results:
            if 'stop_loss' in result:
                print(f"   - {result['ticker']}: Update stop to ₹{result['stop_loss']:.2f}")
        
        print("\n3. POSITION SIZING:")
        avg_factor = np.mean([r['position_factor'] for r in results if 'position_factor' in r])
        print(f"   - Average position size factor: {avg_factor*100:.0f}%")
        print(f"   - Adjust new positions accordingly")
        
        # Save to file
        self._save_report(results, positions)
    
    def _save_report(self, results, positions):
        """Save report to file including HTML format"""
        output_dir = os.path.join(self.base_dir, 'ML-Framework', 'results', 'portfolio_analysis')
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save as CSV
        df = pd.DataFrame(results)
        csv_file = os.path.join(output_dir, f'portfolio_regime_{timestamp}.csv')
        df.to_csv(csv_file, index=False)
        
        # Save as JSON
        json_file = os.path.join(output_dir, f'portfolio_regime_{timestamp}.json')
        with open(json_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'results': results,
                'summary': {
                    'total_positions': len(results),
                    'urgent_actions': len([r for r in results if r.get('action') in ['REDUCE_OR_EXIT', 'CONSIDER_EXIT']])
                }
            }, f, indent=2)
        
        # Generate HTML report
        html_file = os.path.join(output_dir, f'portfolio_regime_{timestamp}.html')
        self._generate_html_report(results, positions, html_file)
        
        print(f"\nReports saved to:")
        print(f"  - {csv_file}")
        print(f"  - {json_file}")
        print(f"  - {html_file}")

    def _generate_html_report(self, results, positions, output_file):
        """Generate comprehensive HTML report with charts and analysis"""
        
        # Calculate summary statistics
        total_value = sum(r['current_price'] * r['quantity'] for r in results if 'error' not in r)
        total_pnl = sum(r['pnl'] for r in results if 'error' not in r)
        total_pnl_pct = (total_pnl / total_value) * 100 if total_value > 0 else 0
        
        # Group by action
        action_groups = {}
        for r in results:
            if 'action' in r:
                action = r['action']
                if action not in action_groups:
                    action_groups[action] = []
                action_groups[action].append(r)
        
        # HTML template
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Portfolio Regime Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .summary-box {{
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .position-card {{
            background-color: white;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 5px solid #3498db;
        }}
        .position-card.urgent {{
            border-left-color: #e74c3c;
        }}
        .position-card.bullish {{
            border-left-color: #27ae60;
        }}
        .position-card.bearish {{
            border-left-color: #e74c3c;
        }}
        .metric {{
            display: inline-block;
            margin-right: 20px;
            padding: 10px;
            background-color: #ecf0f1;
            border-radius: 5px;
        }}
        .action-urgent {{
            color: #e74c3c;
            font-weight: bold;
        }}
        .action-monitor {{
            color: #f39c12;
        }}
        .action-hold {{
            color: #27ae60;
            font-weight: bold;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #34495e;
            color: white;
        }}
        .chart-container {{
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .warning {{
            background-color: #fff3cd;
            border: 1px solid #ffeeba;
            color: #856404;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }}
        .pnl-positive {{ color: #27ae60; }}
        .pnl-negative {{ color: #e74c3c; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Portfolio Regime Analysis</h1>
        <p>Generated on {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}</p>
    </div>
    
    <div class="summary-box">
        <h2>Portfolio Summary</h2>
        <div class="metric">
            <strong>Total Positions:</strong> {len(positions)}
        </div>
        <div class="metric">
            <strong>Total Value:</strong> ₹{total_value:,.2f}
        </div>
        <div class="metric">
            <strong>Total P&L:</strong> 
            <span class="{'pnl-positive' if total_pnl >= 0 else 'pnl-negative'}">
                {'₹+' if total_pnl >= 0 else '₹'}{total_pnl:,.2f} ({'+' if total_pnl_pct >= 0 else ''}{total_pnl_pct:.2f}%)
            </span>
        </div>
    </div>
"""
        
        # Add regime distribution chart if plotly available
        if HAS_PLOTLY:
            regime_counts = {}
            for r in results:
                if 'regime' in r:
                    regime = r['regime']
                    regime_counts[regime] = regime_counts.get(regime, 0) + 1
            
            if regime_counts:
                fig = go.Figure(data=[go.Pie(
                    labels=list(regime_counts.keys()),
                    values=list(regime_counts.values()),
                    hole=0.3
                )])
                fig.update_layout(
                    title="Regime Distribution",
                    showlegend=True,
                    height=400
                )
                
                html_content += f"""
    <div class="chart-container">
        {fig.to_html(full_html=False, include_plotlyjs='cdn')}
    </div>
"""
        
        # Urgent actions section
        urgent_actions = [r for r in results if r.get('action') in ['REDUCE_OR_EXIT', 'CONSIDER_EXIT']]
        if urgent_actions:
            html_content += """
    <div class="warning">
        <h3>⚠️ Urgent Actions Required</h3>
        <ul>
"""
            for r in urgent_actions:
                html_content += f"""            <li><strong>{r['ticker']}</strong>: {r['action']} - 
                Regime ({r['regime']}) opposes {r['position_type']} position</li>
"""
            html_content += """        </ul>
    </div>
"""
        
        # Detailed positions table
        html_content += """
    <div class="summary-box">
        <h2>Detailed Position Analysis</h2>
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Type</th>
                    <th>Entry</th>
                    <th>Current</th>
                    <th>Qty</th>
                    <th>P&L</th>
                    <th>P&L %</th>
                    <th>Regime</th>
                    <th>Action</th>
                    <th>Stop Loss</th>
                    <th>Position Size</th>
                </tr>
            </thead>
            <tbody>
"""
        
        # Sort results by action priority
        action_priority = {
            'REDUCE_OR_EXIT': 1,
            'CONSIDER_EXIT': 2,
            'REDUCE_SIZE': 3,
            'MONITOR': 4,
            'HOLD_OR_ADD': 5
        }
        
        results_sorted = sorted(results, 
                              key=lambda x: action_priority.get(x.get('action', 'MONITOR'), 4))
        
        for r in results_sorted:
            if 'error' not in r:
                pnl_class = 'pnl-positive' if r['pnl'] >= 0 else 'pnl-negative'
                action_class = ''
                if r['action'] in ['REDUCE_OR_EXIT', 'CONSIDER_EXIT']:
                    action_class = 'action-urgent'
                elif r['action'] == 'HOLD_OR_ADD':
                    action_class = 'action-hold'
                else:
                    action_class = 'action-monitor'
                
                html_content += f"""
                <tr>
                    <td><strong>{r['ticker']}</strong></td>
                    <td>{r['position_type']}</td>
                    <td>₹{r['entry_price']:.2f}</td>
                    <td>₹{r['current_price']:.2f}</td>
                    <td>{r['quantity']}</td>
                    <td class="{pnl_class}">₹{r['pnl']:,.2f}</td>
                    <td class="{pnl_class}">{r['pnl_pct']:.2f}%</td>
                    <td>{r['regime']}</td>
                    <td class="{action_class}">{r['action']}</td>
                    <td>₹{r['stop_loss']:.2f}</td>
                    <td>{r['position_factor']*100:.0f}%</td>
                </tr>
"""
        
        html_content += """
            </tbody>
        </table>
    </div>
"""
        
        # Action recommendations section
        html_content += """
    <div class="summary-box">
        <h2>Action Recommendations</h2>
"""
        
        for action, positions_list in sorted(action_groups.items(), 
                                           key=lambda x: action_priority.get(x[0], 4)):
            tickers = [p['ticker'] for p in positions_list]
            
            action_desc = {
                'REDUCE_OR_EXIT': '🔴 Exit or significantly reduce these positions immediately',
                'CONSIDER_EXIT': '🟠 Consider exiting these positions',
                'REDUCE_SIZE': '🟡 Reduce position size due to high volatility',
                'MONITOR': '⚪ Continue monitoring, maintain current position',
                'HOLD_OR_ADD': '🟢 Favorable regime, can hold or add to position'
            }
            
            html_content += f"""
        <div style="margin-bottom: 15px;">
            <h4>{action}</h4>
            <p>{action_desc.get(action, '')}</p>
            <p><strong>Tickers:</strong> {', '.join(tickers)}</p>
        </div>
"""
        
        html_content += """    </div>
"""
        
        # Risk management checklist
        html_content += """
    <div class="summary-box">
        <h2>Risk Management Checklist</h2>
        <ol>
            <li><strong>Update Stop Losses:</strong> Review and update all stop loss orders based on the recommendations above</li>
            <li><strong>Position Sizing:</strong> For new entries, use the position size factors shown (average: {:.0f}%)</li>
            <li><strong>Urgent Actions:</strong> Address all REDUCE_OR_EXIT positions immediately</li>
            <li><strong>High Volatility:</strong> Consider reducing exposure in high volatility regimes</li>
            <li><strong>Regime Alignment:</strong> Ensure your directional bias aligns with market regime</li>
        </ol>
    </div>
""".format(np.mean([r['position_factor'] for r in results if 'position_factor' in r]) * 100)
        
        # Market insights section
        regime_insights = {
            'trending_bullish': 'Strong upward trend detected. Favorable for long positions.',
            'trending_bearish': 'Strong downward trend detected. Favorable for short positions or cash.',
            'ranging_high_vol': 'High volatility ranging market. Reduce position sizes and widen stops.',
            'ranging_low_vol': 'Low volatility consolidation. Wait for breakout before adding positions.',
            'transitioning': 'Market regime is changing. Monitor closely and be ready to adapt.'
        }
        
        html_content += """
    <div class="summary-box">
        <h2>Market Regime Insights</h2>
"""
        
        unique_regimes = set(r['regime'] for r in results if 'regime' in r)
        for regime in unique_regimes:
            count = sum(1 for r in results if r.get('regime') == regime)
            html_content += f"""
        <div style="margin-bottom: 10px;">
            <strong>{regime.replace('_', ' ').title()} ({count} positions):</strong>
            <p>{regime_insights.get(regime, 'Monitor market conditions closely.')}</p>
        </div>
"""
        
        html_content += """
    </div>
    
    <div style="text-align: center; color: #666; margin-top: 40px;">
        <p>Generated by ML-Framework Portfolio Regime Analyzer</p>
        <p>Report timestamp: {}</p>
    </div>
</body>
</html>
""".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # Save HTML file
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        print(f"\nHTML report generated: {output_file}")
        
        # Try to open in browser
        try:
            import webbrowser
            webbrowser.open(f"file://{output_file}")
        except:
            pass

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Portfolio Regime Analysis')
    parser.add_argument('--use-zerodha', action='store_true', 
                       help='Fetch positions from Zerodha API')
    parser.add_argument('--no-html', action='store_true',
                       help='Skip HTML report generation')
    
    args = parser.parse_args()
    
    analyzer = PortfolioRegimeAnalyzer()
    analyzer.generate_portfolio_report(use_zerodha=args.use_zerodha)

if __name__ == "__main__":
    main()