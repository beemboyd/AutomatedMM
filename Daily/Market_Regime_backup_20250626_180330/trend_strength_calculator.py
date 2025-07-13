#!/usr/bin/env python
"""
Trend Strength Calculator
Analyzes Long vs Short reversal scan counts to determine market trend strength
"""

import os
import sys
import logging
import datetime
import json
import pandas as pd
import numpy as np
from glob import glob
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                       "trend_strength_calculator.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TrendStrengthCalculator:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.scan_results_dir = os.path.join(self.script_dir, "scan_results")
        self.output_dir = os.path.join(self.script_dir, "trend_analysis")
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Trend strength thresholds
        self.thresholds = {
            'strong_bullish': 2.0,    # Long/Short ratio > 2.0
            'bullish': 1.5,           # Long/Short ratio > 1.5
            'neutral_bullish': 1.2,   # Long/Short ratio > 1.2
            'neutral': 0.8,           # Long/Short ratio between 0.8 and 1.2
            'neutral_bearish': 0.67,  # Long/Short ratio < 0.8
            'bearish': 0.5,           # Long/Short ratio < 0.67
            'strong_bearish': 0.0     # Long/Short ratio < 0.5
        }
        
    def load_latest_scan(self):
        """Load the most recent scan results"""
        scan_files = glob(os.path.join(self.scan_results_dir, "reversal_scan_*.json"))
        
        if not scan_files:
            logger.warning("No scan result files found")
            return None
            
        # Get the most recent file
        latest_file = max(scan_files, key=os.path.getmtime)
        
        try:
            with open(latest_file, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded scan results from {latest_file}")
            return data
        except Exception as e:
            logger.error(f"Error loading scan results: {e}")
            return None
            
    def load_historical_scans(self, days=30):
        """Load historical scan results for trend analysis"""
        scan_files = glob(os.path.join(self.scan_results_dir, "reversal_scan_*.json"))
        
        historical_data = []
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        
        for file_path in scan_files:
            try:
                # Check file modification time
                if datetime.datetime.fromtimestamp(os.path.getmtime(file_path)) < cutoff_date:
                    continue
                    
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    historical_data.append(data)
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
                continue
                
        # Sort by timestamp
        historical_data.sort(key=lambda x: x['timestamp'])
        
        logger.info(f"Loaded {len(historical_data)} historical scan results")
        return historical_data
        
    def calculate_trend_strength(self, long_count, short_count):
        """Calculate trend strength based on Long/Short ratio"""
        # Handle edge cases
        if long_count == 0 and short_count == 0:
            return 'no_signals', 0.0, 'No reversal patterns detected'
            
        if short_count == 0:
            # All long signals
            return 'strong_bullish', float('inf'), 'Only bullish reversal patterns detected'
            
        # Calculate ratio
        ratio = long_count / short_count
        
        # Determine trend strength
        if ratio > self.thresholds['strong_bullish']:
            trend = 'strong_bullish'
            description = 'Strong bullish trend - Long reversals dominate'
        elif ratio > self.thresholds['bullish']:
            trend = 'bullish'
            description = 'Bullish trend - More long than short reversals'
        elif ratio > self.thresholds['neutral_bullish']:
            trend = 'neutral_bullish'
            description = 'Neutral with bullish bias'
        elif ratio > self.thresholds['neutral']:
            trend = 'neutral'
            description = 'Neutral market - Balanced reversals'
        elif ratio > self.thresholds['neutral_bearish']:
            trend = 'neutral_bearish'
            description = 'Neutral with bearish bias'
        elif ratio > self.thresholds['bearish']:
            trend = 'bearish'
            description = 'Bearish trend - More short than long reversals'
        else:
            trend = 'strong_bearish'
            description = 'Strong bearish trend - Short reversals dominate'
            
        return trend, ratio, description
        
    def calculate_trend_momentum(self, historical_data):
        """Calculate trend momentum based on historical data"""
        if len(historical_data) < 2:
            return 'insufficient_data', 0.0
            
        # Calculate ratios for each scan
        ratios = []
        for scan in historical_data:
            if scan['short_count'] > 0:
                ratio = scan['long_count'] / scan['short_count']
            elif scan['long_count'] > 0:
                ratio = float('inf')
            else:
                ratio = 1.0
            ratios.append(ratio)
            
        # Calculate momentum metrics
        recent_avg = np.mean(ratios[-5:]) if len(ratios) >= 5 else np.mean(ratios)
        overall_avg = np.mean(ratios)
        
        # Determine momentum
        momentum_ratio = recent_avg / overall_avg if overall_avg > 0 else 1.0
        
        if momentum_ratio > 1.2:
            momentum = 'increasing_bullish'
            momentum_desc = 'Trend strengthening toward bullish'
        elif momentum_ratio > 1.05:
            momentum = 'slightly_bullish'
            momentum_desc = 'Slight bullish momentum'
        elif momentum_ratio > 0.95:
            momentum = 'stable'
            momentum_desc = 'Stable trend momentum'
        elif momentum_ratio > 0.8:
            momentum = 'slightly_bearish'
            momentum_desc = 'Slight bearish momentum'
        else:
            momentum = 'increasing_bearish'
            momentum_desc = 'Trend strengthening toward bearish'
            
        return momentum, momentum_ratio, momentum_desc
        
    def generate_trend_report(self, scan_data, historical_data=None):
        """Generate comprehensive trend strength report"""
        # Calculate current trend strength
        trend, ratio, description = self.calculate_trend_strength(
            scan_data['long_count'], 
            scan_data['short_count']
        )
        
        # Calculate momentum if historical data available
        momentum_data = None
        if historical_data and len(historical_data) > 1:
            momentum, momentum_ratio, momentum_desc = self.calculate_trend_momentum(historical_data)
            momentum_data = {
                'momentum': momentum,
                'momentum_ratio': momentum_ratio,
                'description': momentum_desc
            }
            
        # Prepare report data
        report = {
            'timestamp': datetime.datetime.now().isoformat(),
            'scan_timestamp': scan_data['timestamp'],
            'counts': {
                'long': scan_data['long_count'],
                'short': scan_data['short_count'],
                'total': scan_data['long_count'] + scan_data['short_count']
            },
            'trend_strength': {
                'trend': trend,
                'ratio': ratio if ratio != float('inf') else 'inf',
                'description': description
            },
            'momentum': momentum_data,
            'recommendation': self._generate_recommendation(trend, momentum_data)
        }
        
        # Save report
        output_file = os.path.join(self.output_dir, 
                                 f"trend_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Trend report saved to {output_file}")
        
        return report
        
    def _generate_recommendation(self, trend, momentum_data):
        """Generate trading recommendation based on trend and momentum"""
        recommendations = {
            'strong_bullish': {
                'bias': 'Long',
                'confidence': 'High',
                'action': 'Focus on long setups, avoid shorts'
            },
            'bullish': {
                'bias': 'Long',
                'confidence': 'Medium',
                'action': 'Prefer long setups, be selective with shorts'
            },
            'neutral_bullish': {
                'bias': 'Long',
                'confidence': 'Low',
                'action': 'Slight preference for longs, both directions viable'
            },
            'neutral': {
                'bias': 'Neutral',
                'confidence': 'Low',
                'action': 'No directional bias, trade both directions'
            },
            'neutral_bearish': {
                'bias': 'Short',
                'confidence': 'Low',
                'action': 'Slight preference for shorts, both directions viable'
            },
            'bearish': {
                'bias': 'Short',
                'confidence': 'Medium',
                'action': 'Prefer short setups, be selective with longs'
            },
            'strong_bearish': {
                'bias': 'Short',
                'confidence': 'High',
                'action': 'Focus on short setups, avoid longs'
            },
            'no_signals': {
                'bias': 'None',
                'confidence': 'None',
                'action': 'Wait for reversal patterns to develop'
            }
        }
        
        base_recommendation = recommendations.get(trend, recommendations['neutral'])
        
        # Adjust based on momentum
        if momentum_data:
            if momentum_data['momentum'] == 'increasing_bullish' and trend in ['neutral', 'neutral_bearish']:
                base_recommendation['action'] += ' (Momentum shifting bullish)'
            elif momentum_data['momentum'] == 'increasing_bearish' and trend in ['neutral', 'neutral_bullish']:
                base_recommendation['action'] += ' (Momentum shifting bearish)'
                
        return base_recommendation
        
    def analyze_current_trend(self):
        """Analyze current trend strength from latest scan"""
        # Load latest scan
        scan_data = self.load_latest_scan()
        if not scan_data:
            logger.error("No scan data available")
            return None
            
        # Load historical data
        historical_data = self.load_historical_scans(days=30)
        
        # Generate report
        report = self.generate_trend_report(scan_data, historical_data)
        
        return report
        
    def get_scan_history(self, days=7):
        """Get historical scan data for the specified number of days"""
        try:
            # Get all scan result files
            scan_files = sorted(glob(os.path.join(self.scan_results_dir, "reversal_scan_*.json")))
            
            if not scan_files:
                logger.warning("No historical scan files found")
                return []
                
            # Get scan data from the last N days
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
            scan_history = []
            
            for scan_file in scan_files:
                try:
                    with open(scan_file, 'r') as f:
                        data = json.load(f)
                        
                    # Parse timestamp
                    timestamp = datetime.datetime.fromisoformat(data['timestamp'])
                    
                    # Only include recent data
                    if timestamp >= cutoff_date:
                        scan_history.append({
                            'timestamp': data['timestamp'],
                            'long_count': data['long_count'],
                            'short_count': data['short_count']
                        })
                        
                except Exception as e:
                    logger.error(f"Error reading scan file {scan_file}: {e}")
                    continue
                    
            # Sort by timestamp
            scan_history.sort(key=lambda x: x['timestamp'])
            
            logger.info(f"Retrieved {len(scan_history)} historical scan records")
            return scan_history
            
        except Exception as e:
            logger.error(f"Error getting scan history: {e}")
            return []


def main():
    """Main function to calculate trend strength"""
    calculator = TrendStrengthCalculator()
    
    try:
        report = calculator.analyze_current_trend()
        
        if report:
            print("\n===== Trend Strength Analysis =====")
            print(f"Timestamp: {report['timestamp']}")
            print(f"\nReversal Counts:")
            print(f"  Long: {report['counts']['long']}")
            print(f"  Short: {report['counts']['short']}")
            print(f"  Total: {report['counts']['total']}")
            
            print(f"\nTrend Strength:")
            print(f"  Trend: {report['trend_strength']['trend'].upper()}")
            print(f"  Ratio: {report['trend_strength']['ratio']:.2f}" if report['trend_strength']['ratio'] != 'inf' else "  Ratio: Infinite (no shorts)")
            print(f"  Description: {report['trend_strength']['description']}")
            
            if report['momentum']:
                print(f"\nMomentum Analysis:")
                print(f"  Momentum: {report['momentum']['momentum']}")
                print(f"  Momentum Ratio: {report['momentum']['momentum_ratio']:.2f}")
                print(f"  Description: {report['momentum']['description']}")
                
            print(f"\nRecommendation:")
            print(f"  Bias: {report['recommendation']['bias']}")
            print(f"  Confidence: {report['recommendation']['confidence']}")
            print(f"  Action: {report['recommendation']['action']}")
            print("=====================================\n")
            
        return 0
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())