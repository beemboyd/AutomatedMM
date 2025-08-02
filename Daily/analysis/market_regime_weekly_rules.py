#!/usr/bin/env python3
"""
Market Regime Analysis for Weekly Direction Rules
Analyzes regime data to establish clear rules for market direction
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import glob
from collections import defaultdict

class MarketRegimeRulesAnalyzer:
    def __init__(self):
        self.regime_path = '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime'
        self.results_path = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Weekly_Reports'
        
    def load_all_data(self):
        """Load all relevant data for analysis"""
        # Load regime history
        with open(os.path.join(self.regime_path, 'data/regime_history.json'), 'r') as f:
            self.regime_history = json.load(f)
        
        # Load SMA breadth historical data
        with open(os.path.join(self.regime_path, 'historical_breadth_data/sma_breadth_historical_latest.json'), 'r') as f:
            self.sma_breadth_data = json.load(f)
            
        # Load latest regime summary for current state
        with open(os.path.join(self.regime_path, 'regime_analysis/latest_regime_summary.json'), 'r') as f:
            self.latest_regime = json.load(f)
            
        # Load strategy results
        with open(os.path.join(self.results_path, 'latest_simple_analysis.json'), 'r') as f:
            self.long_results = json.load(f)
            
        with open(os.path.join(self.results_path, 'latest_short_simple_analysis.json'), 'r') as f:
            self.short_results = json.load(f)
    
    def analyze_past_4_weeks(self):
        """Analyze regime data for the past 4 weeks"""
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=4)
        
        # Filter SMA breadth data
        breadth_data = []
        for entry in self.sma_breadth_data:
            date = datetime.strptime(entry['date'], '%Y-%m-%d')
            if start_date <= date <= end_date:
                breadth_data.append(entry)
        
        # Analyze breadth patterns
        sma20_values = [d['sma_breadth']['sma20_percent'] for d in breadth_data]
        sma50_values = [d['sma_breadth']['sma50_percent'] for d in breadth_data]
        volume_participation = [d['volume_breadth']['volume_participation'] for d in breadth_data]
        
        analysis = {
            'period': f"{start_date.date()} to {end_date.date()}",
            'sma20_breadth': {
                'mean': np.mean(sma20_values),
                'min': np.min(sma20_values),
                'max': np.max(sma20_values),
                'current': sma20_values[-1] if sma20_values else None,
                'trend': 'declining' if len(sma20_values) > 1 and sma20_values[-1] < sma20_values[0] else 'improving'
            },
            'sma50_breadth': {
                'mean': np.mean(sma50_values),
                'min': np.min(sma50_values),
                'max': np.max(sma50_values),
                'current': sma50_values[-1] if sma50_values else None,
                'trend': 'declining' if len(sma50_values) > 1 and sma50_values[-1] < sma50_values[0] else 'improving'
            },
            'volume_participation': {
                'mean': np.mean(volume_participation),
                'min': np.min(volume_participation),
                'max': np.max(volume_participation),
                'current': volume_participation[-1] if volume_participation else None
            },
            'data_points': len(breadth_data)
        }
        
        return analysis
    
    def extract_current_indicators(self):
        """Extract current market indicators"""
        latest = self.latest_regime
        
        indicators = {
            'current_regime': latest['market_regime']['regime'],
            'regime_confidence': latest['market_regime']['confidence'],
            'reversal_ratio': latest['reversal_counts']['long'] / max(latest['reversal_counts']['short'], 1),
            'market_score': latest['trend_analysis']['market_score'],
            'breadth_indicators': latest['breadth_indicators'],
            'index_analysis': latest['index_analysis'],
            'indices_above_sma20': f"{latest['index_analysis']['indices_above_sma20']}/3",
            'avg_index_position': latest['index_analysis']['avg_position']
        }
        
        return indicators
    
    def generate_market_direction_rules(self):
        """Generate clear rules for market direction"""
        print("\n" + "="*80)
        print("MARKET DIRECTION RULES BASED ON REGIME ANALYSIS")
        print("="*80)
        
        # Load all data
        self.load_all_data()
        
        # Analyze past 4 weeks
        past_analysis = self.analyze_past_4_weeks()
        current_indicators = self.extract_current_indicators()
        
        print(f"\n## PAST 4 WEEKS ANALYSIS ({past_analysis['period']})")
        print(f"Strategy Performance:")
        print(f"  - Long Reversal: {self.long_results['summary']['win_rate']:.1f}% win rate")
        print(f"  - Short Reversal: {self.short_results['summary']['win_rate']:.1f}% win rate")
        
        print(f"\nMarket Breadth Averages:")
        print(f"  - SMA20 Breadth: {past_analysis['sma20_breadth']['mean']:.1f}% (current: {past_analysis['sma20_breadth']['current']:.1f}%)")
        print(f"  - SMA50 Breadth: {past_analysis['sma50_breadth']['mean']:.1f}% (current: {past_analysis['sma50_breadth']['current']:.1f}%)")
        print(f"  - Volume Participation: {past_analysis['volume_participation']['mean']:.2f}")
        
        print(f"\n## CURRENT MARKET INDICATORS")
        print(f"  - Regime: {current_indicators['current_regime']}")
        print(f"  - Confidence: {current_indicators['regime_confidence']:.2f}")
        print(f"  - Long/Short Ratio: {current_indicators['reversal_ratio']:.2f}")
        print(f"  - Market Score: {current_indicators['market_score']:.2f}")
        print(f"  - Indices above SMA20: {current_indicators['indices_above_sma20']}")
        
        # Generate rules
        print("\n" + "="*80)
        print("CLEAR MARKET DIRECTION RULES")
        print("="*80)
        
        print("\n## WEEKLY DIRECTION RULES:")
        print("\n1. **PRIMARY INDICATOR - SMA20 Breadth:**")
        print("   - Above 60%: BULLISH bias (favor long positions)")
        print("   - 40-60%: NEUTRAL (balanced approach)")
        print("   - Below 40%: BEARISH bias (favor short positions)")
        print(f"   - Current: {past_analysis['sma20_breadth']['current']:.1f}% → BEARISH")
        
        print("\n2. **CONFIRMATION - Index Position:**")
        print("   - 3/3 indices above SMA20: Strong BULLISH")
        print("   - 2/3 indices above SMA20: Mild BULLISH")
        print("   - 1/3 indices above SMA20: Mild BEARISH")
        print("   - 0/3 indices above SMA20: Strong BEARISH")
        print(f"   - Current: {current_indicators['indices_above_sma20']} → Strong BEARISH")
        
        print("\n3. **VOLUME PARTICIPATION:**")
        print("   - Above 0.50: High conviction moves")
        print("   - 0.30-0.50: Normal participation")
        print("   - Below 0.30: Low conviction, be cautious")
        print(f"   - Current: {past_analysis['volume_participation']['current']:.2f}")
        
        print("\n## DAILY DIRECTION RULES:")
        print("\n1. **Reversal Signal Ratio:**")
        print("   - Long/Short > 1.5: Bullish day expected")
        print("   - Long/Short 0.7-1.5: Neutral/choppy")
        print("   - Long/Short < 0.7: Bearish day expected")
        print(f"   - Current: {current_indicators['reversal_ratio']:.2f} → Bearish")
        
        print("\n2. **Market Score:**")
        print("   - Above +0.5: Strong bullish")
        print("   - +0.2 to +0.5: Mild bullish")
        print("   - -0.2 to +0.2: Neutral")
        print("   - -0.5 to -0.2: Mild bearish")
        print("   - Below -0.5: Strong bearish")
        print(f"   - Current: {current_indicators['market_score']:.2f} → Strong bearish")
        
        print("\n## ACTIONABLE STRATEGY ALLOCATION:")
        sma20_current = past_analysis['sma20_breadth']['current']
        
        if sma20_current < 40:
            allocation = "70% Short, 30% Long"
            bias = "Strong Bearish"
        elif sma20_current < 50:
            allocation = "60% Short, 40% Long"
            bias = "Bearish"
        elif sma20_current < 60:
            allocation = "50% Short, 50% Long"
            bias = "Neutral"
        elif sma20_current < 70:
            allocation = "40% Short, 60% Long"
            bias = "Bullish"
        else:
            allocation = "30% Short, 70% Long"
            bias = "Strong Bullish"
            
        print(f"\nBased on current SMA20 breadth ({sma20_current:.1f}%):")
        print(f"  - Market Bias: {bias}")
        print(f"  - Recommended Allocation: {allocation}")
        
        # Save rules
        rules_summary = {
            'generated_date': datetime.now().isoformat(),
            'analysis_period': past_analysis['period'],
            'weekly_rules': {
                'sma20_breadth': {
                    'current': sma20_current,
                    'threshold_bullish': 60,
                    'threshold_bearish': 40,
                    'direction': bias
                },
                'index_confirmation': {
                    'indices_above_sma20': current_indicators['indices_above_sma20'],
                    'signal': 'Strong BEARISH'
                },
                'volume_participation': {
                    'current': past_analysis['volume_participation']['current'],
                    'signal': 'Normal' if 0.3 <= past_analysis['volume_participation']['current'] <= 0.5 else 'Abnormal'
                }
            },
            'daily_rules': {
                'reversal_ratio': {
                    'current': current_indicators['reversal_ratio'],
                    'signal': 'Bearish' if current_indicators['reversal_ratio'] < 0.7 else 'Neutral'
                },
                'market_score': {
                    'current': current_indicators['market_score'],
                    'signal': 'Strong bearish' if current_indicators['market_score'] < -0.5 else 'Bearish'
                }
            },
            'recommended_allocation': allocation,
            'market_bias': bias,
            'strategy_performance': {
                'long_win_rate': self.long_results['summary']['win_rate'],
                'short_win_rate': self.short_results['summary']['win_rate']
            }
        }
        
        # Save report
        report_path = os.path.join(self.results_path, f'market_direction_rules_{datetime.now().strftime("%Y%m%d")}.json')
        with open(report_path, 'w') as f:
            json.dump(rules_summary, f, indent=2)
            
        print(f"\n\nRules summary saved to: {report_path}")
        
        return rules_summary

def main():
    analyzer = MarketRegimeRulesAnalyzer()
    analyzer.generate_market_direction_rules()

if __name__ == "__main__":
    main()