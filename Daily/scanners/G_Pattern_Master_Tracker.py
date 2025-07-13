#!/usr/bin/env python
"""
G Pattern Master Tracker
Tracks pattern progression over multiple days and provides actionable recommendations
"""

import os
import pandas as pd
import datetime
import json
from pathlib import Path
import glob
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "g_pattern_master_tracker.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Define paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "results")
MASTER_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "G_Pattern_Master")
MASTER_FILE = os.path.join(MASTER_DIR, "G_Pattern_Master_List.xlsx")
HISTORY_FILE = os.path.join(MASTER_DIR, "G_Pattern_History.json")

# Ensure directories exist
os.makedirs(MASTER_DIR, exist_ok=True)

class GPatternTracker:
    def __init__(self):
        self.history = self.load_history()
        self.today = datetime.datetime.now().strftime("%Y-%m-%d")
        
    def load_history(self):
        """Load historical pattern data"""
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        return {}
    
    def save_history(self):
        """Save pattern history"""
        with open(HISTORY_FILE, 'w') as f:
            json.dump(self.history, f, indent=4)
    
    def get_latest_scan_results(self):
        """Get the most recent KC scan results"""
        pattern = os.path.join(RESULTS_DIR, "KC_Upper_Limit_Trending_*.xlsx")
        files = glob.glob(pattern)
        
        if not files:
            logger.warning("No KC scan results found")
            return pd.DataFrame()
        
        # Get the most recent file
        latest_file = max(files, key=os.path.getctime)
        logger.info(f"Loading scan results from: {latest_file}")
        
        return pd.read_excel(latest_file)
    
    def update_pattern_history(self, ticker, pattern_data):
        """Update history for a ticker"""
        if ticker not in self.history:
            self.history[ticker] = {
                'first_seen': self.today,
                'days_tracked': 0,
                'pattern_progression': [],
                'max_score': 0,
                'recommendation': 'WATCH ONLY'
            }
        
        history = self.history[ticker]
        history['days_tracked'] += 1
        history['last_seen'] = self.today
        
        # Track pattern progression
        progression = {
            'date': self.today,
            'pattern': pattern_data['Pattern'],
            'score': pattern_data['Probability_Score'],
            'h2_days': pattern_data.get('H2_Days_Week', 0),
            'volume_surges': pattern_data.get('Volume_Surge_Days', 0),
            'has_h2': pattern_data.get('Has_H2', False),
            'building_momentum': pattern_data.get('Building_Momentum', False)
        }
        history['pattern_progression'].append(progression)
        
        # Update max score
        if pattern_data['Probability_Score'] > history['max_score']:
            history['max_score'] = pattern_data['Probability_Score']
        
        # Determine recommendation
        history['recommendation'] = self.get_recommendation(ticker, pattern_data)
        
        return history
    
    def get_recommendation(self, ticker, current_data):
        """Get trading recommendation based on pattern progression"""
        history = self.history.get(ticker, {})
        days_tracked = history.get('days_tracked', 0)
        max_score = history.get('max_score', 0)
        current_score = current_data['Probability_Score']
        pattern = current_data['Pattern']
        
        # Decision logic based on pattern and progression
        if pattern == 'G_Pattern' and current_data.get('Volume_Surge_Days', 0) >= 1:
            return "G PATTERN CONFIRMED - FULL POSITION (100%)"
        
        elif pattern == 'Building_G' and days_tracked >= 2:
            if current_data.get('H2_Days_Week', 0) >= 2:
                return "G PATTERN DEVELOPING - DOUBLE POSITION (50%)"
            else:
                return "G PATTERN DEVELOPING - INITIAL POSITION (25%)"
        
        elif pattern in ['H2_Momentum_Start', 'KC_Multi_H2'] and current_score >= 50:
            return "PATTERN EMERGING - INITIAL POSITION (25%)"
        
        elif current_score >= 40 and current_score < 50:
            return "WATCH CLOSELY - PRE-ENTRY"
        
        elif days_tracked >= 5 and max_score >= 70:
            return "HOLD AND MONITOR - PATTERN MATURE"
        
        else:
            return "WATCH ONLY"
    
    def generate_master_report(self):
        """Generate the master tracking report"""
        # Get latest scan results
        scan_df = self.get_latest_scan_results()
        
        if scan_df.empty:
            logger.warning("No scan results to process")
            return
        
        # Update history for each ticker
        master_data = []
        
        for idx, row in scan_df.iterrows():
            ticker = row['Ticker']
            history = self.update_pattern_history(ticker, row)
            
            # Prepare master record
            master_record = {
                'Ticker': ticker,
                'Sector': row['Sector'],
                'Current_Pattern': row['Pattern'],
                'Current_Score': row['Probability_Score'],
                'Days_Tracked': history['days_tracked'],
                'First_Seen': history['first_seen'],
                'Max_Score': history['max_score'],
                'H2_Days': row.get('H2_Days_Week', 0),
                'Volume_Surges': row.get('Volume_Surge_Days', 0),
                'Recommendation': history['recommendation'],
                'Current_Price': row['Entry_Price'],
                'Stop_Loss': row['Stop_Loss'],
                'Target1': row['Target1'],
                'Risk_Reward': row['Risk_Reward_Ratio']
            }
            master_data.append(master_record)
        
        # Create master DataFrame
        master_df = pd.DataFrame(master_data)
        
        # Sort by recommendation priority and score
        recommendation_priority = {
            "G PATTERN CONFIRMED - FULL POSITION (100%)": 1,
            "G PATTERN DEVELOPING - DOUBLE POSITION (50%)": 2,
            "G PATTERN DEVELOPING - INITIAL POSITION (25%)": 3,
            "PATTERN EMERGING - INITIAL POSITION (25%)": 4,
            "HOLD AND MONITOR - PATTERN MATURE": 5,
            "WATCH CLOSELY - PRE-ENTRY": 6,
            "WATCH ONLY": 7
        }
        
        master_df['Priority'] = master_df['Recommendation'].map(recommendation_priority)
        master_df = master_df.sort_values(['Priority', 'Current_Score'], ascending=[True, False])
        master_df = master_df.drop('Priority', axis=1)
        
        # Save master list
        master_df.to_excel(MASTER_FILE, index=False)
        logger.info(f"Master list saved to: {MASTER_FILE}")
        
        # Save history
        self.save_history()
        
        # Generate summary report
        self.generate_summary_report(master_df)
        
        return master_df
    
    def generate_summary_report(self, master_df):
        """Generate a summary report"""
        today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
        summary_file = os.path.join(MASTER_DIR, "G_Pattern_Summary.txt")
        
        with open(summary_file, 'w') as f:
            f.write(f"=== G PATTERN MASTER SUMMARY ===\n")
            f.write(f"Generated: {today}\n")
            f.write(f"Total Patterns Tracked: {len(master_df)}\n\n")
            
            # Group by recommendation
            for rec in master_df['Recommendation'].unique():
                stocks = master_df[master_df['Recommendation'] == rec]
                if len(stocks) > 0:
                    f.write(f"\n{rec} ({len(stocks)} stocks):\n")
                    f.write("-" * 50 + "\n")
                    for idx, stock in stocks.iterrows():
                        f.write(f"{stock['Ticker']} ({stock['Sector']}): ")
                        f.write(f"Score {stock['Current_Score']:.0f}, ")
                        f.write(f"Days {stock['Days_Tracked']}, ")
                        f.write(f"Entry ₹{stock['Current_Price']:.2f}\n")
            
            f.write("\n" + "=" * 50 + "\n")
            f.write("WEEKLY ACTION PLAN:\n")
            f.write("1. FULL POSITION: Stocks with confirmed G Pattern + Volume\n")
            f.write("2. DOUBLE POSITION: Building G with 2+ H2 days\n")
            f.write("3. INITIAL POSITION: Emerging patterns (score 50+)\n")
            f.write("4. WATCH: Pre-entry patterns developing\n")
        
        logger.info(f"Summary report saved to: {summary_file}")
        print(f"\n📊 MASTER REPORTS GENERATED:")
        print(f"1. Master List: {MASTER_FILE}")
        print(f"2. Summary: {summary_file}")
        print(f"3. History: {HISTORY_FILE}")

def main():
    """Main function to run the master tracker"""
    tracker = GPatternTracker()
    master_df = tracker.generate_master_report()
    
    if master_df is not None and not master_df.empty:
        print("\n🎯 TOP RECOMMENDATIONS:")
        top_recs = master_df.head(10)
        for idx, row in top_recs.iterrows():
            print(f"{row['Ticker']}: {row['Recommendation']}")

if __name__ == "__main__":
    main()