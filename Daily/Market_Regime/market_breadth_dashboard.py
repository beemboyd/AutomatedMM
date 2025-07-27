#!/usr/bin/env python3
"""
Enhanced Market Breadth Dashboard
Displays comprehensive market internals from Market Breadth Scanner
Runs on port 5001 for testing alongside existing dashboard
"""

from flask import Flask, render_template, jsonify
import json
import os
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
import logging
from sector_rotation_analyzer import SectorRotationAnalyzer
import pytz

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, 
           template_folder='templates',
           static_folder='static')

# Configuration
BREADTH_DATA_DIR = os.path.join(os.path.dirname(__file__), 'breadth_data')
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 5001
IST = pytz.timezone('Asia/Kolkata')

def get_latest_breadth_data():
    """Get the latest market breadth data"""
    try:
        latest_file = os.path.join(BREADTH_DATA_DIR, 'market_breadth_latest.json')
        if os.path.exists(latest_file):
            with open(latest_file, 'r') as f:
                return json.load(f)
        else:
            return None
    except Exception as e:
        logger.error(f"Error loading breadth data: {e}")
        return None

def get_previous_breadth_data():
    """Get the previous run's breadth data"""
    try:
        # Get all breadth files sorted by timestamp
        breadth_files = sorted([f for f in os.listdir(BREADTH_DATA_DIR) 
                               if f.startswith('market_breadth_') and f.endswith('.json') 
                               and 'latest' not in f])
        
        if len(breadth_files) < 2:
            return None
            
        # Get the second-to-last file (previous run)
        previous_file = os.path.join(BREADTH_DATA_DIR, breadth_files[-2])
        
        with open(previous_file, 'r') as f:
            return json.load(f)
            
    except Exception as e:
        logger.error(f"Error loading previous breadth data: {e}")
        return None

def calculate_sma_changes(current_data, previous_data):
    """Calculate percentage changes in SMA breadth from previous run"""
    if not current_data or not previous_data:
        return None
        
    try:
        current_sma = current_data.get('sma_breadth', {})
        previous_sma = previous_data.get('sma_breadth', {})
        
        # Calculate percentage point changes
        sma20_change = current_sma.get('sma20_percent', 0) - previous_sma.get('sma20_percent', 0)
        sma50_change = current_sma.get('sma50_percent', 0) - previous_sma.get('sma50_percent', 0)
        
        # Calculate relative percentage changes
        sma20_relative_change = (sma20_change / previous_sma.get('sma20_percent', 1)) * 100 if previous_sma.get('sma20_percent', 0) > 0 else 0
        sma50_relative_change = (sma50_change / previous_sma.get('sma50_percent', 1)) * 100 if previous_sma.get('sma50_percent', 0) > 0 else 0
        
        return {
            'sma20_change': round(sma20_change, 2),
            'sma50_change': round(sma50_change, 2),
            'sma20_relative_change': round(sma20_relative_change, 2),
            'sma50_relative_change': round(sma50_relative_change, 2),
            'previous_timestamp': previous_data.get('timestamp', '')
        }
        
    except Exception as e:
        logger.error(f"Error calculating SMA changes: {e}")
        return None

def calculate_position_recommendations(breadth_data):
    """Calculate position sizing and strategy recommendations"""
    if not breadth_data:
        return {
            'position_size_multiplier': 1.0,
            'recommended_strategy': 'Neutral',
            'stop_loss_adjustment': 0
        }
    
    market_score = breadth_data.get('market_score', 0.5)
    regime = breadth_data.get('market_regime', 'Choppy/Sideways')
    sma20_percent = breadth_data['sma_breadth']['sma20_percent']
    
    # Position size multiplier based on market conditions
    if regime == "Strong Uptrend":
        position_multiplier = 1.5
        strategy = "Aggressive Long"
        sl_adjustment = 1.0  # Wider stops in strong trends
    elif regime == "Uptrend":
        position_multiplier = 1.25
        strategy = "Long Bias"
        sl_adjustment = 0.5
    elif regime == "Strong Downtrend":
        position_multiplier = 0.5
        strategy = "Defensive/Short"
        sl_adjustment = -1.0  # Tighter stops
    elif regime == "Downtrend":
        position_multiplier = 0.75
        strategy = "Cautious"
        sl_adjustment = -0.5
    else:
        position_multiplier = 1.0
        strategy = "Neutral/Selective"
        sl_adjustment = 0
    
    return {
        'position_size_multiplier': position_multiplier,
        'recommended_strategy': strategy,
        'stop_loss_adjustment': sl_adjustment,
        'confidence_level': min(100, abs(market_score - 0.5) * 200)  # 0-100 scale
    }

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('market_breadth_dashboard.html')

@app.route('/api/breadth-data')
def get_breadth_data():
    """API endpoint for breadth data"""
    data = get_latest_breadth_data()
    if data:
        # Add position recommendations
        recommendations = calculate_position_recommendations(data)
        data['recommendations'] = recommendations
        
        # Calculate additional metrics for display
        data['advance_decline_ratio'] = {
            'sma20': data['sma_breadth']['above_sma20'] / max(data['sma_breadth']['below_sma20'], 1),
            'sma50': data['sma_breadth']['above_sma50'] / max(data['sma_breadth']['below_sma50'], 1),
            'momentum_5d': data['momentum_indicators']['positive_5d'] / max(data['momentum_indicators']['negative_5d'], 1)
        }
        
        # Add SMA changes from previous run
        previous_data = get_previous_breadth_data()
        sma_changes = calculate_sma_changes(data, previous_data)
        if sma_changes:
            data['sma_changes'] = sma_changes
        
        return jsonify(data)
    else:
        return jsonify({'error': 'No data available'}), 404

@app.route('/api/sector-performance')
def get_sector_performance():
    """API endpoint for sector performance data"""
    data = get_latest_breadth_data()
    if data and 'sector_performance' in data:
        # Format sector data for visualization
        sectors = []
        for sector, metrics in data['sector_performance'].items():
            # Calculate percentages
            above_sma20 = metrics.get('above_sma20', 0) * 100
            above_sma50 = metrics.get('above_sma50', 0) * 100
            rsi = metrics.get('rsi', 50)
            momentum_5d = metrics.get('momentum_5d', 0)
            momentum_10d = metrics.get('momentum_10d', 0)
            
            # Determine market stance
            if above_sma20 >= 65 and above_sma50 >= 65:
                if momentum_5d > 2:
                    stance = "Strong Bullish"
                else:
                    stance = "Bullish"
            elif above_sma20 >= 50 and above_sma50 >= 50:
                stance = "Stable Bullish"
            elif above_sma20 <= 35 and above_sma50 <= 35:
                if momentum_5d < -2:
                    stance = "Strong Bearish"
                else:
                    stance = "Bearish"
            elif above_sma20 <= 50 and above_sma50 <= 50:
                stance = "Weak"
            else:
                stance = "Neutral"
            
            # Determine RSI status
            if rsi >= 70:
                rsi_status = "Overbought"
                rsi_caution = " (caution)"
            elif rsi <= 30:
                rsi_status = "Oversold"
                rsi_caution = " (opportunity)"
            elif rsi >= 60:
                rsi_status = "Strong"
                rsi_caution = ""
            elif rsi <= 40:
                rsi_status = "Weak"
                rsi_caution = ""
            else:
                rsi_status = "Neutral"
                rsi_caution = ""
            
            sectors.append({
                'sector': sector,
                'stance': stance,
                'above_sma20': above_sma20,
                'above_sma50': above_sma50,
                'avg_rsi': rsi,
                'rsi_status': rsi_status,
                'rsi_caution': rsi_caution,
                'momentum_5d': momentum_5d,
                'momentum_10d': momentum_10d
            })
        
        # Sort by momentum
        sectors.sort(key=lambda x: x['momentum_5d'], reverse=True)
        return jsonify(sectors)
    else:
        return jsonify([]), 404

@app.route('/api/stock-details')
def get_stock_details():
    """API endpoint for individual stock details"""
    data = get_latest_breadth_data()
    if data and 'stocks' in data:
        stocks = data['stocks']
        
        # Sort by different criteria for different views
        top_gainers = sorted(stocks, key=lambda x: x['momentum_5d'], reverse=True)[:10]
        top_losers = sorted(stocks, key=lambda x: x['momentum_5d'])[:10]
        high_volume = sorted(stocks, key=lambda x: x['volume_ratio'], reverse=True)[:10]
        overbought = [s for s in stocks if s['rsi'] > 70]
        oversold = [s for s in stocks if s['rsi'] < 30]
        
        return jsonify({
            'top_gainers': top_gainers,
            'top_losers': top_losers,
            'high_volume': high_volume,
            'overbought': overbought[:10],
            'oversold': oversold[:10]
        })
    else:
        return jsonify({}), 404

@app.route('/api/historical-breadth')
def get_historical_breadth():
    """API endpoint for historical breadth data (last 10 scans)"""
    try:
        # Get all breadth files sorted by timestamp
        breadth_files = sorted([f for f in os.listdir(BREADTH_DATA_DIR) 
                               if f.startswith('market_breadth_') and f.endswith('.json') 
                               and 'latest' not in f])
        
        # Get last 10 files
        recent_files = breadth_files[-10:] if len(breadth_files) > 10 else breadth_files
        
        historical_data = []
        for filename in recent_files:
            filepath = os.path.join(BREADTH_DATA_DIR, filename)
            with open(filepath, 'r') as f:
                data = json.load(f)
                historical_data.append({
                    'timestamp': data['timestamp'],
                    'market_score': data['market_score'],
                    'sma20_percent': data['sma_breadth']['sma20_percent'],
                    'sma50_percent': data['sma_breadth']['sma50_percent'],
                    'avg_rsi': data['rsi_distribution']['avg_rsi'],
                    'regime': data['market_regime']
                })
        
        return jsonify(historical_data)
    except Exception as e:
        logger.error(f"Error loading historical data: {e}")
        return jsonify([]), 404

@app.route('/api/early-bird')
def get_early_bird():
    """API endpoint for Early Bird (KC_Breakout_Watch first appearances)"""
    try:
        # Get the latest KC Upper Limit results
        kc_results_dir = os.path.join(os.path.dirname(SCRIPT_DIR), 'results')
        
        # Find today's KC files
        today = datetime.now(IST).strftime('%Y%m%d')
        kc_files = sorted([f for f in os.listdir(kc_results_dir) 
                          if f.startswith(f'KC_Upper_Limit_Trending_{today}') 
                          and f.endswith('.xlsx')])
        
        if not kc_files:
            # Try yesterday if no files today
            yesterday = (datetime.now(IST) - timedelta(days=1)).strftime('%Y%m%d')
            kc_files = sorted([f for f in os.listdir(kc_results_dir) 
                              if f.startswith(f'KC_Upper_Limit_Trending_{yesterday}') 
                              and f.endswith('.xlsx')])
        
        early_birds = []
        seen_tickers = set()
        
        # Process files chronologically to find first appearances
        for filename in kc_files:
            filepath = os.path.join(kc_results_dir, filename)
            try:
                df = pd.read_excel(filepath)
                
                # Filter for KC_Breakout_Watch pattern
                kc_breakout = df[df['Pattern'] == 'KC_Breakout_Watch']
                
                for _, row in kc_breakout.iterrows():
                    ticker = row['Ticker']
                    if ticker not in seen_tickers:
                        seen_tickers.add(ticker)
                        
                        # Extract timestamp from filename (YYYYMMDD_HHMMSS)
                        timestamp_str = filename.replace('KC_Upper_Limit_Trending_', '').replace('.xlsx', '')
                        time_parts = timestamp_str.split('_')
                        if len(time_parts) == 2:
                            hour = time_parts[1][:2]
                            minute = time_parts[1][2:4]
                            time_str = f"{hour}:{minute}"
                        else:
                            time_str = "N/A"
                        
                        early_birds.append({
                            'ticker': ticker,
                            'sector': row.get('Sector', 'Unknown'),
                            'entry_price': round(row.get('Entry_Price', 0), 2),
                            'stop_loss': round(row.get('Stop_Loss', 0), 2),
                            'target1': round(row.get('Target1', 0), 2),
                            'probability_score': round(row.get('Probability_Score', 0), 1),
                            'volume_ratio': round(row.get('Volume_Ratio', 0), 2),
                            'time_appeared': time_str,
                            'description': row.get('Description', ''),
                            'kc_distance': round(row.get('KC_Distance_%', 0), 2)
                        })
            except Exception as e:
                logger.error(f"Error processing KC file {filename}: {e}")
                continue
        
        # Sort by probability score descending
        early_birds.sort(key=lambda x: x['probability_score'], reverse=True)
        
        return jsonify({
            'early_birds': early_birds[:10],  # Top 10
            'total_count': len(early_birds)
        })
        
    except Exception as e:
        logger.error(f"Error getting Early Bird data: {e}")
        return jsonify({'early_birds': [], 'total_count': 0})

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'port': PORT})

@app.route('/test')
def test_page():
    """Test page for diagnostics"""
    return render_template('test.html')

@app.route('/api/sma-breadth-history')
def get_sma_breadth_history():
    """Get historical SMA breadth data for charting - 7 months of data"""
    try:
        # Check for historical data file first
        historical_data_file = os.path.join(SCRIPT_DIR, 'historical_breadth_data', 'sma_breadth_historical_latest.json')
        
        labels = []
        sma20_values = []
        sma50_values = []
        
        if os.path.exists(historical_data_file):
            # Use the 7-month historical data
            try:
                with open(historical_data_file, 'r') as f:
                    historical_data = json.load(f)
                
                # Process historical data
                for day_data in historical_data:
                    # Parse the date
                    date_str = day_data.get('date', '')
                    if date_str:
                        # Convert to proper date format for Chart.js time scale
                        try:
                            from datetime import datetime
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            formatted_date = date_obj.strftime('%Y-%m-%d')
                            # Add data point
                            labels.append(formatted_date)
                            sma20_values.append(day_data.get('sma_breadth', {}).get('sma20_percent', 0))
                            sma50_values.append(day_data.get('sma_breadth', {}).get('sma50_percent', 0))
                        except Exception as e:
                            logger.error(f"Error parsing date {date_str}: {e}")
                            continue
                
                logger.info(f"Loaded {len(labels)} days of historical SMA breadth data")
                
            except Exception as e:
                logger.error(f"Error loading historical data: {e}")
        
        # If no historical data or it's empty, fall back to current breadth data
        if not labels:
            logger.warning("No historical data found, falling back to current breadth data")
            
            if os.path.exists(BREADTH_DATA_DIR):
                # Get all breadth files except 'latest'
                all_files = [f for f in os.listdir(BREADTH_DATA_DIR) 
                            if f.startswith('market_breadth_') and f.endswith('.json') 
                            and 'latest' not in f]
                
                # Sort by filename (which includes timestamp)
                all_files.sort()
                
                # Take the last 30 days worth of data (assuming ~14 files per day)
                breadth_files = all_files[-420:]  # 30 days * 14 files/day
                
                # Process each file
                for filename in breadth_files:
                    filepath = os.path.join(BREADTH_DATA_DIR, filename)
                    try:
                        with open(filepath, 'r') as f:
                            data = json.load(f)
                        
                        # Extract timestamp from data
                        timestamp_str = data.get('timestamp', '')
                        if timestamp_str:
                            # Parse the timestamp
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            
                            # Format label as daily date only
                            date_str = timestamp.strftime('%Y-%m-%d')
                            
                            # Add data point (daily aggregation)
                            labels.append(date_str)
                            sma20_values.append(data.get('sma_breadth', {}).get('sma20_percent', 0))
                            sma50_values.append(data.get('sma_breadth', {}).get('sma50_percent', 0))
                        
                    except Exception as e:
                        logger.error(f"Error processing breadth file {filename}: {e}")
                        continue
        
        # Downsample for better chart display (keep every nth point for optimal viewing)
        if len(labels) > 100:
            step = max(1, len(labels) // 100)
            labels = labels[::step]
            sma20_values = sma20_values[::step]
            sma50_values = sma50_values[::step]
        
        return jsonify({
            'labels': labels,
            'sma20_values': sma20_values,
            'sma50_values': sma50_values,
            'data_points': len(labels)
        })
        
    except Exception as e:
        logger.error(f"Error fetching SMA breadth history: {e}")
        return jsonify({
            'error': str(e),
            'labels': [],
            'sma20_values': [],
            'sma50_values': [],
            'data_points': 0
        })

@app.route('/api/sector-rotation')
def get_sector_rotation():
    """API endpoint for sector rotation analysis"""
    try:
        analyzer = SectorRotationAnalyzer()
        
        # Get rotation events
        rotations = analyzer.detect_rotation_events(lookback_days=30)
        
        # Get statistics
        stats = analyzer.get_rotation_statistics(days=90)
        
        # Get predictions
        predictions = analyzer.predict_next_rotation(lookback_days=30)
        
        # Get current cycle phase
        cycle_phase = analyzer._determine_market_cycle_phase()
        
        analyzer.close()
        
        return jsonify({
            'rotation_events': rotations,
            'statistics': stats,
            'predictions': predictions,
            'current_cycle_phase': cycle_phase
        })
    except Exception as e:
        logger.error(f"Error getting sector rotation data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sector-cycles/<sector>')
def get_sector_cycles(sector):
    """API endpoint for individual sector cycle analysis"""
    try:
        analyzer = SectorRotationAnalyzer()
        
        # Get cycles for the sector
        cycles = analyzer.identify_sector_cycles(sector, min_cycle_days=20)
        
        analyzer.close()
        
        return jsonify({
            'sector': sector,
            'cycles': cycles,
            'total_cycles': len(cycles),
            'avg_cycle_duration': sum(c['duration_days'] for c in cycles) / len(cycles) if cycles else 0
        })
    except Exception as e:
        logger.error(f"Error getting sector cycle data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rotation-report')
def get_rotation_report():
    """API endpoint for comprehensive rotation report"""
    try:
        analyzer = SectorRotationAnalyzer()
        report = analyzer.generate_rotation_report()
        analyzer.close()
        
        return jsonify(report)
    except Exception as e:
        logger.error(f"Error generating rotation report: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create directories if they don't exist
    Path(BREADTH_DATA_DIR).mkdir(parents=True, exist_ok=True)
    
    # Create template and static directories
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    Path(template_dir).mkdir(exist_ok=True)
    Path(static_dir).mkdir(exist_ok=True)
    
    # Log current working directory and paths
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Template directory: {template_dir}")
    logger.info(f"Template exists: {os.path.exists(os.path.join(template_dir, 'market_breadth_dashboard.html'))}")
    logger.info(f"Data directory: {BREADTH_DATA_DIR}")
    logger.info(f"Latest data exists: {os.path.exists(os.path.join(BREADTH_DATA_DIR, 'market_breadth_latest.json'))}")
    
    logger.info(f"Starting Market Breadth Dashboard on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=True)