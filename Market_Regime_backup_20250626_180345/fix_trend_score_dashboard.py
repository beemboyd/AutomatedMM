#!/usr/bin/env python3
"""
Fix for trend_score showing as 0 in the dashboard
This script patches the market_indicators to include trend_score from the database
"""

import os
import sys
import sqlite3
from datetime import datetime, timedelta

def get_latest_trend_score():
    """Get the latest trend_score from the database"""
    try:
        db_path = "/Users/maverick/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get the most recent trend_score
        cursor.execute("""
            SELECT trend_score, timestamp 
            FROM predictions 
            WHERE trend_score IS NOT NULL 
            ORDER BY timestamp DESC 
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            trend_score, timestamp = result
            # Check if it's recent (within last hour)
            ts = datetime.fromisoformat(timestamp.replace(' ', 'T'))
            if datetime.now() - ts < timedelta(hours=1):
                return float(trend_score)
        
        return None
        
    except Exception as e:
        print(f"Error getting trend_score from database: {e}")
        return None

def patch_market_indicators():
    """Add method to get trend_score to market_indicators"""
    
    # Read the market_indicators.py file
    file_path = "/Users/maverick/PycharmProjects/India-TS/Market_Regime/core/market_indicators.py"
    
    # Create the patch code to add
    patch_code = '''
    def get_trend_score_from_db(self) -> float:
        """Get the latest trend_score from regime analysis database"""
        try:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'data', 'regime_learning.db'
            )
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get the most recent trend_score
            cursor.execute("""
                SELECT trend_score, timestamp 
                FROM predictions 
                WHERE trend_score IS NOT NULL 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                trend_score, timestamp = result
                # Check if it's recent (within last hour)
                from datetime import datetime, timedelta
                ts = datetime.fromisoformat(timestamp.replace(' ', 'T'))
                if datetime.now() - ts < timedelta(hours=1):
                    return float(trend_score)
            
            # Fallback: calculate from latest scanner results
            return self._calculate_trend_score_from_files()
            
        except Exception as e:
            self.logger.error(f"Error getting trend_score from database: {e}")
            return 0.0
    
    def _calculate_trend_score_from_files(self) -> float:
        """Calculate trend score from latest scanner result files"""
        try:
            import glob
            import json
            
            # Find latest regime summary
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            summary_file = os.path.join(base_path, '..', 'Daily', 'Market_Regime', 
                                      'regime_analysis', 'latest_regime_summary.json')
            
            if os.path.exists(summary_file):
                with open(summary_file, 'r') as f:
                    data = json.load(f)
                    if 'trend_analysis' in data and 'ratio' in data['trend_analysis']:
                        ratio = data['trend_analysis']['ratio']
                        if ratio != 'inf':
                            return float(ratio)
            
            return 1.0  # Default neutral
            
        except Exception as e:
            self.logger.error(f"Error calculating trend_score from files: {e}")
            return 1.0
'''
    
    print("Patch code to add to market_indicators.py:")
    print("=" * 60)
    print(patch_code)
    print("=" * 60)
    
    # Also need to update calculate_all_indicators to include trend_score
    update_code = '''
In the calculate_all_indicators method, after composite_scores, add:

        # Add trend score from database/files
        indicators['trend_score'] = self.get_trend_score_from_db()
'''
    
    print("\nUpdate needed in calculate_all_indicators method:")
    print("=" * 60)
    print(update_code)
    print("=" * 60)

def main():
    print("Trend Score Dashboard Fix")
    print("=" * 60)
    
    # Check current trend_score
    trend_score = get_latest_trend_score()
    if trend_score:
        print(f"Latest trend_score in database: {trend_score}")
    else:
        print("No recent trend_score found in database")
    
    # Show patch instructions
    print("\nTo fix the dashboard showing trend_score as 0:")
    patch_market_indicators()
    
    print("\nAlternatively, for a quick fix without modifying code:")
    print("1. Ensure market_regime_analyzer.py is running and saving to database")
    print("2. Check that regime analysis is calculating trend_score properly")
    print("3. Restart the dashboard after regime analysis runs")

if __name__ == "__main__":
    main()