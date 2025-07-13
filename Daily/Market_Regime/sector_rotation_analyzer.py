#!/usr/bin/env python3
"""
Sector Rotation Analyzer
Tracks and analyzes sector rotation patterns to identify market cycles
"""

import pandas as pd
import numpy as np
import json
import sqlite3
from datetime import datetime, timedelta
import os
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SectorRotationAnalyzer:
    def __init__(self, db_path=None):
        """Initialize the analyzer with database connection"""
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), 'sector_rotation.db')
        
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
        
    def _create_tables(self):
        """Create necessary database tables"""
        cursor = self.conn.cursor()
        
        # Historical sector performance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sector_performance (
                date TEXT,
                sector TEXT,
                above_sma20 REAL,
                above_sma50 REAL,
                avg_rsi REAL,
                momentum_5d REAL,
                momentum_10d REAL,
                relative_strength REAL,
                sector_rank INTEGER,
                PRIMARY KEY (date, sector)
            )
        ''')
        
        # Sector rotation events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rotation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                from_sector TEXT,
                to_sector TEXT,
                rotation_strength REAL,
                event_type TEXT
            )
        ''')
        
        # Sector cycle metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sector_cycles (
                sector TEXT,
                cycle_start TEXT,
                cycle_end TEXT,
                duration_days INTEGER,
                peak_performance REAL,
                trough_performance REAL,
                cycle_type TEXT,
                PRIMARY KEY (sector, cycle_start)
            )
        ''')
        
        self.conn.commit()
    
    def store_daily_performance(self, date, sector_data):
        """Store daily sector performance data"""
        cursor = self.conn.cursor()
        
        # Calculate relative strength for each sector
        sectors = []
        for sector, metrics in sector_data.items():
            sectors.append({
                'sector': sector,
                'above_sma20': metrics.get('above_sma20', 0),
                'above_sma50': metrics.get('above_sma50', 0),
                'avg_rsi': metrics.get('rsi', 50),
                'momentum_5d': metrics.get('momentum_5d', 0),
                'momentum_10d': metrics.get('momentum_10d', 0)
            })
        
        # Calculate relative strength score
        for sector in sectors:
            # Composite score based on multiple factors
            sector['relative_strength'] = (
                sector['above_sma20'] * 0.3 +
                sector['above_sma50'] * 0.2 +
                (sector['avg_rsi'] - 50) / 50 * 0.2 +
                sector['momentum_5d'] / 100 * 0.15 +
                sector['momentum_10d'] / 100 * 0.15
            )
        
        # Rank sectors by relative strength
        sectors.sort(key=lambda x: x['relative_strength'], reverse=True)
        for i, sector in enumerate(sectors):
            sector['sector_rank'] = i + 1
        
        # Store in database
        for sector in sectors:
            cursor.execute('''
                INSERT OR REPLACE INTO sector_performance 
                (date, sector, above_sma20, above_sma50, avg_rsi, momentum_5d, 
                 momentum_10d, relative_strength, sector_rank)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                date, sector['sector'], sector['above_sma20'], 
                sector['above_sma50'], sector['avg_rsi'], 
                sector['momentum_5d'], sector['momentum_10d'],
                sector['relative_strength'], sector['sector_rank']
            ))
        
        self.conn.commit()
        return sectors
    
    def detect_rotation_events(self, lookback_days=5):
        """Detect sector rotation events based on ranking changes"""
        cursor = self.conn.cursor()
        
        # Get recent data
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT date, sector, sector_rank, relative_strength
            FROM sector_performance
            WHERE date >= ? AND date <= ?
            ORDER BY date, sector_rank
        ''', (start_date, end_date))
        
        data = cursor.fetchall()
        if not data:
            return []
        
        # Group by date
        date_rankings = {}
        for row in data:
            date = row[0]
            if date not in date_rankings:
                date_rankings[date] = []
            date_rankings[date].append({
                'sector': row[1],
                'rank': row[2],
                'strength': row[3]
            })
        
        # Detect rotations
        dates = sorted(date_rankings.keys())
        rotations = []
        
        for i in range(1, len(dates)):
            prev_date = dates[i-1]
            curr_date = dates[i]
            
            prev_rankings = {s['sector']: s for s in date_rankings[prev_date]}
            curr_rankings = {s['sector']: s for s in date_rankings[curr_date]}
            
            # Check for significant rank changes
            for sector in curr_rankings:
                if sector in prev_rankings:
                    rank_change = prev_rankings[sector]['rank'] - curr_rankings[sector]['rank']
                    
                    # Significant improvement (moved up 2+ ranks)
                    if rank_change >= 2:
                        rotations.append({
                            'date': curr_date,
                            'sector': sector,
                            'event_type': 'EMERGING_LEADER',
                            'rank_change': rank_change,
                            'new_rank': curr_rankings[sector]['rank']
                        })
                    
                    # Significant decline (moved down 2+ ranks)
                    elif rank_change <= -2:
                        rotations.append({
                            'date': curr_date,
                            'sector': sector,
                            'event_type': 'LOSING_MOMENTUM',
                            'rank_change': rank_change,
                            'new_rank': curr_rankings[sector]['rank']
                        })
            
            # Check for leadership changes
            if len(prev_rankings) > 0 and len(curr_rankings) > 0:
                prev_leader = min(prev_rankings.values(), key=lambda x: x['rank'])['sector']
                curr_leader = min(curr_rankings.values(), key=lambda x: x['rank'])['sector']
                
                if prev_leader != curr_leader:
                    rotations.append({
                        'date': curr_date,
                        'from_sector': prev_leader,
                        'to_sector': curr_leader,
                        'event_type': 'LEADERSHIP_CHANGE'
                    })
        
        return rotations
    
    def identify_sector_cycles(self, sector, min_cycle_days=20):
        """Identify bullish and bearish cycles for a sector"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT date, relative_strength, momentum_10d
            FROM sector_performance
            WHERE sector = ?
            ORDER BY date
        ''', (sector,))
        
        data = cursor.fetchall()
        if len(data) < min_cycle_days:
            return []
        
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(data, columns=['date', 'relative_strength', 'momentum_10d'])
        df['date'] = pd.to_datetime(df['date'])
        
        # Identify turning points using rolling averages
        df['rs_ma'] = df['relative_strength'].rolling(window=5).mean()
        df['rs_trend'] = df['rs_ma'].diff()
        
        cycles = []
        current_cycle = None
        
        for i in range(1, len(df)):
            # Detect cycle start (trough to uptrend)
            if (current_cycle is None and 
                df.iloc[i]['rs_trend'] > 0 and 
                df.iloc[i-1]['rs_trend'] <= 0):
                
                current_cycle = {
                    'start_date': df.iloc[i]['date'],
                    'start_idx': i,
                    'type': 'BULLISH'
                }
            
            # Detect cycle end (peak to downtrend)
            elif (current_cycle and 
                  current_cycle['type'] == 'BULLISH' and
                  df.iloc[i]['rs_trend'] < 0 and 
                  df.iloc[i-1]['rs_trend'] >= 0):
                
                duration = (df.iloc[i]['date'] - current_cycle['start_date']).days
                
                if duration >= min_cycle_days:
                    cycle_data = df.iloc[current_cycle['start_idx']:i+1]
                    cycles.append({
                        'sector': sector,
                        'cycle_start': current_cycle['start_date'].strftime('%Y-%m-%d'),
                        'cycle_end': df.iloc[i]['date'].strftime('%Y-%m-%d'),
                        'duration_days': duration,
                        'peak_performance': cycle_data['relative_strength'].max(),
                        'trough_performance': cycle_data['relative_strength'].min(),
                        'cycle_type': 'BULLISH'
                    })
                
                current_cycle = {
                    'start_date': df.iloc[i]['date'],
                    'start_idx': i,
                    'type': 'BEARISH'
                }
        
        return cycles
    
    def get_rotation_statistics(self, days=90):
        """Get sector rotation statistics for the specified period"""
        cursor = self.conn.cursor()
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Average time at top
        cursor.execute('''
            SELECT sector, COUNT(*) as days_at_top
            FROM sector_performance
            WHERE date >= ? AND date <= ? AND sector_rank = 1
            GROUP BY sector
        ''', (start_date, end_date))
        
        leadership_data = cursor.fetchall()
        
        # Rotation frequency
        cursor.execute('''
            SELECT COUNT(DISTINCT date) as rotation_count
            FROM (
                SELECT date, 
                       LAG(sector) OVER (ORDER BY date) as prev_leader,
                       sector
                FROM sector_performance
                WHERE sector_rank = 1 AND date >= ? AND date <= ?
            )
            WHERE prev_leader != sector
        ''', (start_date, end_date))
        
        rotation_freq = cursor.fetchone()[0]
        
        # Sector momentum persistence
        cursor.execute('''
            SELECT sector, 
                   AVG(CASE WHEN momentum_5d > 0 THEN 1 ELSE 0 END) as positive_momentum_pct,
                   AVG(ABS(momentum_5d)) as avg_momentum_magnitude
            FROM sector_performance
            WHERE date >= ? AND date <= ?
            GROUP BY sector
        ''', (start_date, end_date))
        
        momentum_data = cursor.fetchall()
        
        return {
            'leadership_duration': {row[0]: row[1] for row in leadership_data},
            'rotation_frequency': rotation_freq,
            'avg_days_between_rotations': days / max(rotation_freq, 1),
            'sector_momentum': {row[0]: {'positive_pct': row[1], 'avg_magnitude': row[2]} 
                               for row in momentum_data}
        }
    
    def predict_next_rotation(self, lookback_days=30):
        """Predict potential next sector rotation based on momentum trends"""
        cursor = self.conn.cursor()
        
        # Get recent trends
        cursor.execute('''
            SELECT sector,
                   AVG(momentum_5d) as recent_momentum,
                   AVG(momentum_10d) as medium_momentum,
                   MAX(sector_rank) - MIN(sector_rank) as rank_volatility,
                   AVG(relative_strength) as avg_strength
            FROM sector_performance
            WHERE date >= date('now', '-' || ? || ' days')
            GROUP BY sector
        ''', (lookback_days,))
        
        data = cursor.fetchall()
        
        predictions = []
        for row in data:
            sector = row[0]
            
            # Score based on improving momentum and low current rank
            momentum_improvement = row[1] - row[2]  # 5d vs 10d momentum
            
            prediction_score = (
                momentum_improvement * 0.4 +  # Momentum improvement
                (1 / (row[3] + 1)) * 0.3 +   # Lower volatility is better
                row[4] * 0.3                  # Current strength
            )
            
            predictions.append({
                'sector': sector,
                'rotation_probability': min(max(prediction_score * 100, 0), 100),
                'momentum_trend': 'IMPROVING' if momentum_improvement > 0 else 'DECLINING',
                'current_strength': row[4]
            })
        
        predictions.sort(key=lambda x: x['rotation_probability'], reverse=True)
        return predictions[:5]  # Top 5 candidates
    
    def generate_rotation_report(self, output_path=None):
        """Generate comprehensive sector rotation report"""
        report = {
            'generated_at': datetime.now().isoformat(),
            'rotation_events': self.detect_rotation_events(lookback_days=30),
            'statistics': self.get_rotation_statistics(days=90),
            'predictions': self.predict_next_rotation(),
            'current_cycle_phase': self._determine_market_cycle_phase()
        }
        
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
        
        return report
    
    def _determine_market_cycle_phase(self):
        """Determine current phase of market cycle based on sector patterns"""
        cursor = self.conn.cursor()
        
        # Get recent sector leadership patterns
        cursor.execute('''
            SELECT sector, sector_rank
            FROM sector_performance
            WHERE date = (SELECT MAX(date) FROM sector_performance)
            ORDER BY sector_rank
        ''')
        
        current_rankings = cursor.fetchall()
        
        if not current_rankings:
            return "UNKNOWN"
        
        # Simplified cycle determination based on leading sectors
        leaders = [row[0] for row in current_rankings[:3]]
        
        # Market cycle phases based on typical sector rotation
        if any(s in leaders for s in ['Technology', 'Consumer Cyclical']):
            phase = "EARLY_EXPANSION"
        elif any(s in leaders for s in ['Industrials', 'Basic Materials']):
            phase = "MID_EXPANSION"
        elif any(s in leaders for s in ['Energy', 'Utilities']):
            phase = "LATE_EXPANSION"
        elif any(s in leaders for s in ['Consumer Defensive', 'Healthcare']):
            phase = "CONTRACTION"
        else:
            phase = "TRANSITIONAL"
        
        return phase
    
    def close(self):
        """Close database connection"""
        self.conn.close()


if __name__ == "__main__":
    # Example usage
    analyzer = SectorRotationAnalyzer()
    
    # Load latest sector data from market breadth
    breadth_file = os.path.join(os.path.dirname(__file__), 'breadth_data', 'market_breadth_latest.json')
    if os.path.exists(breadth_file):
        with open(breadth_file, 'r') as f:
            data = json.load(f)
        
        if 'sector_performance' in data:
            date = data['timestamp'].split('T')[0]
            analyzer.store_daily_performance(date, data['sector_performance'])
    
    # Generate report
    report = analyzer.generate_rotation_report()
    print(json.dumps(report, indent=2))
    
    analyzer.close()