#!/usr/bin/env python3
"""
VSR Exit Optimization Dashboard
Real-time monitoring dashboard for VSR patterns and exit signals
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash
from dash import dcc, html, Input, Output, State
import dash_table
import json
import os
import sys

# Add parent directory to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ..user_context_manager import UserContextManager

class VSRExitDashboard:
    def __init__(self):
        self.app = dash.Dash(__name__)
        self.user_context = UserContextManager().get_default_context()
        self.kite = self.user_context.kite
        self.positions = {}
        self.alerts = []
        
    def calculate_vsr(self, high, low, volume):
        """Calculate Volume Spread Ratio"""
        spread = high - low
        return volume / spread if spread > 0 else 0
    
    def check_exit_signals(self, symbol, candles_df):
        """Check for VSR-based exit signals"""
        signals = []
        
        if len(candles_df) < 3:
            return signals
        
        # Get entry candle (first candle)
        entry_candle = candles_df.iloc[0]
        entry_vsr = self.calculate_vsr(entry_candle['high'], entry_candle['low'], entry_candle['volume'])
        
        # Check last 3 candles
        recent_candles = candles_df.tail(3)
        
        # Signal 1: VSR Deterioration
        current_vsr = self.calculate_vsr(
            recent_candles.iloc[-1]['high'],
            recent_candles.iloc[-1]['low'],
            recent_candles.iloc[-1]['volume']
        )
        
        if current_vsr < 0.5 * entry_vsr:
            signals.append({
                'type': 'VSR_DETERIORATION',
                'severity': 'HIGH',
                'message': f'VSR dropped to {current_vsr:.0f} from entry {entry_vsr:.0f}'
            })
        
        # Signal 2: Three consecutive red candles
        red_count = sum(recent_candles['close'] < recent_candles['open'])
        if red_count == 3:
            signals.append({
                'type': 'THREE_RED_CANDLES',
                'severity': 'HIGH',
                'message': 'Three consecutive red candles detected'
            })
        
        # Signal 3: Shooting star pattern
        last_candle = recent_candles.iloc[-1]
        body = abs(last_candle['close'] - last_candle['open'])
        total_range = last_candle['high'] - last_candle['low']
        upper_shadow = last_candle['high'] - max(last_candle['open'], last_candle['close'])
        
        if total_range > 0:
            upper_shadow_ratio = upper_shadow / total_range
            if upper_shadow_ratio > 0.6:
                signals.append({
                    'type': 'SHOOTING_STAR',
                    'severity': 'MEDIUM',
                    'message': f'Shooting star pattern ({upper_shadow_ratio*100:.0f}% upper shadow)'
                })
        
        return signals
    
    def create_layout(self):
        """Create dashboard layout"""
        self.app.layout = html.Div([
            html.H1("VSR Exit Optimization Dashboard", style={'textAlign': 'center'}),
            
            # Controls
            html.Div([
                html.Div([
                    html.Label("Add Position to Monitor:"),
                    dcc.Input(id='symbol-input', type='text', placeholder='Symbol'),
                    dcc.Input(id='entry-price-input', type='number', placeholder='Entry Price'),
                    html.Button('Add Position', id='add-position-btn', n_clicks=0)
                ], style={'width': '48%', 'display': 'inline-block'}),
                
                html.Div([
                    html.Label("Refresh Interval:"),
                    dcc.Dropdown(
                        id='refresh-interval',
                        options=[
                            {'label': '5 seconds', 'value': 5000},
                            {'label': '10 seconds', 'value': 10000},
                            {'label': '30 seconds', 'value': 30000},
                            {'label': '1 minute', 'value': 60000}
                        ],
                        value=10000
                    )
                ], style={'width': '48%', 'float': 'right', 'display': 'inline-block'})
            ], style={'padding': '20px'}),
            
            # Alerts section
            html.Div(id='alerts-container', style={'padding': '20px'}),
            
            # Positions table
            html.Div([
                html.H3("Monitored Positions"),
                dash_table.DataTable(
                    id='positions-table',
                    columns=[
                        {'name': 'Symbol', 'id': 'symbol'},
                        {'name': 'Entry Price', 'id': 'entry_price', 'type': 'numeric', 'format': {'specifier': '.2f'}},
                        {'name': 'Current Price', 'id': 'current_price', 'type': 'numeric', 'format': {'specifier': '.2f'}},
                        {'name': 'P&L %', 'id': 'pnl_pct', 'type': 'numeric', 'format': {'specifier': '.2f'}},
                        {'name': 'Entry VSR', 'id': 'entry_vsr', 'type': 'numeric', 'format': {'specifier': '.0f'}},
                        {'name': 'Current VSR', 'id': 'current_vsr', 'type': 'numeric', 'format': {'specifier': '.0f'}},
                        {'name': 'VSR Ratio', 'id': 'vsr_ratio', 'type': 'numeric', 'format': {'specifier': '.2f'}},
                        {'name': 'Exit Signals', 'id': 'signals'},
                        {'name': 'Action', 'id': 'action'}
                    ],
                    data=[],
                    style_cell={'textAlign': 'center'},
                    style_data_conditional=[
                        {
                            'if': {'column_id': 'pnl_pct', 'filter_query': '{pnl_pct} < 0'},
                            'backgroundColor': '#ffcccc'
                        },
                        {
                            'if': {'column_id': 'pnl_pct', 'filter_query': '{pnl_pct} > 0'},
                            'backgroundColor': '#ccffcc'
                        },
                        {
                            'if': {'column_id': 'action', 'filter_query': '{action} contains "EXIT"'},
                            'backgroundColor': '#ff6666',
                            'color': 'white',
                            'fontWeight': 'bold'
                        }
                    ]
                )
            ], style={'padding': '20px'}),
            
            # Charts section
            html.Div(id='charts-container', style={'padding': '20px'}),
            
            # Auto-refresh
            dcc.Interval(id='interval-component', interval=10000, n_intervals=0),
            
            # Hidden div to store positions data
            html.Div(id='positions-store', style={'display': 'none'})
        ])
    
    def setup_callbacks(self):
        """Setup dashboard callbacks"""
        
        @self.app.callback(
            Output('positions-store', 'children'),
            [Input('add-position-btn', 'n_clicks')],
            [State('symbol-input', 'value'),
             State('entry-price-input', 'value'),
             State('positions-store', 'children')]
        )
        def add_position(n_clicks, symbol, entry_price, positions_json):
            if n_clicks == 0 or not symbol or not entry_price:
                return positions_json
            
            # Load existing positions
            if positions_json:
                positions = json.loads(positions_json)
            else:
                positions = {}
            
            # Add new position
            positions[symbol] = {
                'entry_price': entry_price,
                'entry_time': datetime.now().isoformat(),
                'entry_vsr': 0  # Will be calculated on first update
            }
            
            return json.dumps(positions)
        
        @self.app.callback(
            [Output('positions-table', 'data'),
             Output('alerts-container', 'children'),
             Output('charts-container', 'children')],
            [Input('interval-component', 'n_intervals'),
             Input('positions-store', 'children')]
        )
        def update_dashboard(n_intervals, positions_json):
            if not positions_json:
                return [], [], []
            
            positions = json.loads(positions_json)
            table_data = []
            alerts = []
            charts = []
            
            for symbol, position in positions.items():
                try:
                    # Get current price
                    ltp_data = self.kite.ltp([f'NSE:{symbol}'])
                    current_price = ltp_data[f'NSE:{symbol}']['last_price']
                    
                    # Get 5-minute data
                    instruments = self.kite.ltp([f'NSE:{symbol}'])
                    instrument_token = list(instruments.values())[0]['instrument_token']
                    
                    # Fetch last 30 minutes of 5-minute data
                    to_date = datetime.now()
                    from_date = to_date - timedelta(minutes=30)
                    
                    candles = self.kite.historical_data(
                        instrument_token,
                        from_date,
                        to_date,
                        '5minute'
                    )
                    
                    if candles:
                        df = pd.DataFrame(candles)
                        
                        # Calculate current VSR
                        last_candle = df.iloc[-1]
                        current_vsr = self.calculate_vsr(
                            last_candle['high'],
                            last_candle['low'],
                            last_candle['volume']
                        )
                        
                        # Calculate entry VSR if not set
                        if position['entry_vsr'] == 0:
                            entry_candle = df.iloc[0]
                            position['entry_vsr'] = self.calculate_vsr(
                                entry_candle['high'],
                                entry_candle['low'],
                                entry_candle['volume']
                            )
                        
                        # Check exit signals
                        signals = self.check_exit_signals(symbol, df)
                        
                        # Determine action
                        high_severity_signals = [s for s in signals if s['severity'] == 'HIGH']
                        action = 'EXIT NOW' if len(high_severity_signals) >= 2 else \
                                'WATCH' if len(signals) > 0 else 'HOLD'
                        
                        # Calculate P&L
                        pnl_pct = ((current_price - position['entry_price']) / position['entry_price']) * 100
                        
                        # Add to table
                        table_data.append({
                            'symbol': symbol,
                            'entry_price': position['entry_price'],
                            'current_price': current_price,
                            'pnl_pct': pnl_pct,
                            'entry_vsr': position['entry_vsr'],
                            'current_vsr': current_vsr,
                            'vsr_ratio': current_vsr / position['entry_vsr'] if position['entry_vsr'] > 0 else 0,
                            'signals': ', '.join([s['type'] for s in signals]),
                            'action': action
                        })
                        
                        # Add alerts
                        if signals:
                            for signal in signals:
                                alerts.append(
                                    html.Div([
                                        html.Strong(f"{symbol}: "),
                                        html.Span(signal['message']),
                                        html.Span(f" [{signal['severity']}]", 
                                                style={'color': 'red' if signal['severity'] == 'HIGH' else 'orange'})
                                    ], style={'padding': '5px', 'backgroundColor': '#fff3cd', 'margin': '5px'})
                                )
                        
                        # Create chart
                        fig = make_subplots(
                            rows=2, cols=1,
                            shared_xaxes=True,
                            vertical_spacing=0.03,
                            subplot_titles=(f'{symbol} Price', 'VSR'),
                            row_heights=[0.7, 0.3]
                        )
                        
                        # Price chart
                        fig.add_trace(
                            go.Candlestick(
                                x=df['date'],
                                open=df['open'],
                                high=df['high'],
                                low=df['low'],
                                close=df['close'],
                                name='Price'
                            ),
                            row=1, col=1
                        )
                        
                        # Entry line
                        fig.add_hline(
                            y=position['entry_price'],
                            line_dash="dash",
                            line_color="blue",
                            annotation_text="Entry",
                            row=1, col=1
                        )
                        
                        # VSR chart
                        df['vsr'] = df.apply(lambda r: self.calculate_vsr(r['high'], r['low'], r['volume']), axis=1)
                        fig.add_trace(
                            go.Bar(x=df['date'], y=df['vsr'], name='VSR'),
                            row=2, col=1
                        )
                        
                        # VSR threshold line
                        fig.add_hline(
                            y=position['entry_vsr'] * 0.5,
                            line_dash="dash",
                            line_color="red",
                            annotation_text="50% Entry VSR",
                            row=2, col=1
                        )
                        
                        fig.update_layout(
                            height=400,
                            showlegend=False,
                            margin=dict(l=0, r=0, t=30, b=0)
                        )
                        
                        charts.append(
                            html.Div([
                                dcc.Graph(figure=fig)
                            ], style={'width': '48%', 'display': 'inline-block', 'padding': '10px'})
                        )
                        
                except Exception as e:
                    print(f"Error updating {symbol}: {e}")
                    table_data.append({
                        'symbol': symbol,
                        'entry_price': position['entry_price'],
                        'current_price': 'Error',
                        'pnl_pct': 0,
                        'entry_vsr': 0,
                        'current_vsr': 0,
                        'vsr_ratio': 0,
                        'signals': 'Error',
                        'action': 'CHECK'
                    })
            
            # Add alert header if alerts exist
            if alerts:
                alerts.insert(0, html.H3("⚠️ Active Alerts", style={'color': 'red'}))
            
            return table_data, alerts, charts
    
    def run(self, debug=True, port=8050):
        """Run the dashboard"""
        self.create_layout()
        self.setup_callbacks()
        print(f"Starting VSR Exit Dashboard on http://localhost:{port}")
        self.app.run_server(debug=debug, port=port)


if __name__ == "__main__":
    dashboard = VSRExitDashboard()
    dashboard.run()