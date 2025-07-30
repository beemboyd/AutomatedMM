#!/usr/bin/env python3
"""
Hourly-Daily Confluence Analyzer
Identifies tickers showing persistence in both hourly and daily scans
for early detection of strong momentum moves
"""

import os
import sys
import json
import datetime
from collections import defaultdict
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class HourlyDailyConfluenceAnalyzer:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(self.base_dir, 'data')
        
        # Persistence files
        self.daily_persistence_file = os.path.join(self.data_dir, 'vsr_ticker_persistence.json')
        self.hourly_persistence_file = os.path.join(self.data_dir, 'vsr_ticker_persistence_hourly_long.json')
        
        # Load data
        self.daily_data = self._load_json(self.daily_persistence_file)
        self.hourly_data = self._load_json(self.hourly_persistence_file)
        
    def _load_json(self, filepath):
        """Load JSON data from file"""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return {'tickers': {}}
    
    def analyze_confluence(self):
        """Analyze confluence between hourly and daily persistence"""
        results = {
            'confluence_tickers': [],  # Tickers in both hourly and daily
            'emerging_tickers': [],    # Strong hourly, not yet in daily
            'established_tickers': [],  # Strong daily with hourly support
            'analysis_time': datetime.datetime.now().isoformat()
        }
        
        hourly_tickers = set(self.hourly_data.get('tickers', {}).keys())
        daily_tickers = set(self.daily_data.get('tickers', {}).keys())
        
        # 1. Confluence Tickers (in both)
        confluence = hourly_tickers & daily_tickers
        for ticker in confluence:
            hourly_info = self.hourly_data['tickers'][ticker]
            daily_info = self.daily_data['tickers'][ticker]
            
            # Calculate strength scores
            hourly_strength = self._calculate_strength(hourly_info, 'hourly')
            daily_strength = self._calculate_strength(daily_info, 'daily')
            
            results['confluence_tickers'].append({
                'ticker': ticker,
                'hourly_appearances': hourly_info['appearances'],
                'daily_appearances': daily_info['appearances'],
                'hourly_momentum_avg': self._avg_momentum(hourly_info),
                'daily_momentum_avg': self._avg_momentum(daily_info),
                'hourly_strength': hourly_strength,
                'daily_strength': daily_strength,
                'confluence_score': (hourly_strength + daily_strength) / 2,
                'signal': self._get_signal_strength(hourly_info, daily_info)
            })
        
        # 2. Emerging Tickers (strong hourly, not in daily yet)
        emerging = hourly_tickers - daily_tickers
        for ticker in emerging:
            hourly_info = self.hourly_data['tickers'][ticker]
            if hourly_info['appearances'] >= 2:  # At least 2 hourly appearances
                hourly_strength = self._calculate_strength(hourly_info, 'hourly')
                results['emerging_tickers'].append({
                    'ticker': ticker,
                    'hourly_appearances': hourly_info['appearances'],
                    'hourly_momentum_avg': self._avg_momentum(hourly_info),
                    'hourly_strength': hourly_strength,
                    'first_seen': hourly_info['first_seen'],
                    'potential': 'HIGH' if hourly_strength > 70 else 'MEDIUM'
                })
        
        # 3. Established Tickers (in daily with recent hourly activity)
        for ticker in daily_tickers:
            daily_info = self.daily_data['tickers'][ticker]
            if ticker in hourly_tickers:
                hourly_info = self.hourly_data['tickers'][ticker]
                # Check if hourly activity is recent (within last 24 hours)
                last_hourly = datetime.datetime.fromisoformat(hourly_info['last_seen'])
                if (datetime.datetime.now() - last_hourly).total_seconds() < 86400:
                    daily_strength = self._calculate_strength(daily_info, 'daily')
                    results['established_tickers'].append({
                        'ticker': ticker,
                        'daily_days': daily_info['days_tracked'],
                        'daily_appearances': daily_info['appearances'],
                        'hourly_support': True,
                        'momentum_consistency': self._check_momentum_consistency(hourly_info, daily_info),
                        'strength': daily_strength
                    })
        
        # Sort results by strength/score
        results['confluence_tickers'].sort(key=lambda x: x['confluence_score'], reverse=True)
        results['emerging_tickers'].sort(key=lambda x: x['hourly_strength'], reverse=True)
        results['established_tickers'].sort(key=lambda x: x['strength'], reverse=True)
        
        return results
    
    def _calculate_strength(self, ticker_info, timeframe):
        """Calculate strength score for a ticker"""
        score = 0
        
        # Appearance score
        if timeframe == 'hourly':
            score += min(ticker_info['appearances'] * 10, 30)  # Max 30 points
        else:
            score += min(ticker_info['appearances'] * 5, 30)   # Max 30 points
        
        # Momentum score
        avg_momentum = self._avg_momentum(ticker_info)
        if avg_momentum > 7:
            score += 30
        elif avg_momentum > 5:
            score += 20
        elif avg_momentum > 3:
            score += 10
        
        # Consistency score
        if ticker_info['positive_momentum_days'] > 0:
            consistency = ticker_info['positive_momentum_days'] / max(ticker_info['days_tracked'], 1)
            score += consistency * 20  # Max 20 points
        
        # Recency score
        if ticker_info.get('last_positive_momentum'):
            last_momentum = datetime.datetime.fromisoformat(ticker_info['last_positive_momentum'])
            hours_ago = (datetime.datetime.now() - last_momentum).total_seconds() / 3600
            if hours_ago < 6:
                score += 20
            elif hours_ago < 12:
                score += 10
            elif hours_ago < 24:
                score += 5
        
        return min(score, 100)  # Cap at 100
    
    def _avg_momentum(self, ticker_info):
        """Calculate average momentum from history"""
        history = ticker_info.get('momentum_history', [])
        if not history:
            return 0
        
        momentums = [h['momentum'] for h in history if h['momentum'] > 0]
        return sum(momentums) / len(momentums) if momentums else 0
    
    def _get_signal_strength(self, hourly_info, daily_info):
        """Determine signal strength based on confluence"""
        hourly_avg = self._avg_momentum(hourly_info)
        daily_avg = self._avg_momentum(daily_info)
        
        if hourly_avg > 5 and daily_avg > 5:
            return "STRONG"
        elif hourly_avg > 3 and daily_avg > 3:
            return "MEDIUM"
        else:
            return "WEAK"
    
    def _check_momentum_consistency(self, hourly_info, daily_info):
        """Check if momentum is consistent between timeframes"""
        hourly_avg = self._avg_momentum(hourly_info)
        daily_avg = self._avg_momentum(daily_info)
        
        if abs(hourly_avg - daily_avg) < 2:
            return "HIGH"
        elif abs(hourly_avg - daily_avg) < 4:
            return "MEDIUM"
        else:
            return "LOW"
    
    def generate_alert_candidates(self, results):
        """Generate list of tickers that should trigger alerts"""
        alerts = []
        
        # High confluence alerts
        for ticker in results['confluence_tickers'][:5]:  # Top 5
            if ticker['confluence_score'] > 70 and ticker['signal'] in ['STRONG', 'MEDIUM']:
                alerts.append({
                    'ticker': ticker['ticker'],
                    'type': 'CONFLUENCE',
                    'message': f"{ticker['ticker']} showing strong hourly+daily confluence (Score: {ticker['confluence_score']:.0f})",
                    'priority': 'HIGH'
                })
        
        # Emerging ticker alerts
        for ticker in results['emerging_tickers'][:3]:  # Top 3
            if ticker['hourly_strength'] > 70:
                alerts.append({
                    'ticker': ticker['ticker'],
                    'type': 'EMERGING',
                    'message': f"{ticker['ticker']} emerging with strong hourly momentum ({ticker['hourly_appearances']} appearances)",
                    'priority': 'MEDIUM'
                })
        
        return alerts
    
    def print_analysis(self, results):
        """Print analysis results"""
        print("\n" + "="*80)
        print("HOURLY-DAILY CONFLUENCE ANALYSIS")
        print("="*80)
        print(f"Analysis Time: {results['analysis_time']}")
        
        # Confluence tickers
        print(f"\n📊 CONFLUENCE TICKERS (In Both Hourly & Daily): {len(results['confluence_tickers'])}")
        print("-"*80)
        if results['confluence_tickers']:
            print(f"{'Ticker':<10} {'Score':<8} {'Signal':<10} {'Hourly':<15} {'Daily':<15} {'Avg Mom':<10}")
            print("-"*80)
            for t in results['confluence_tickers'][:10]:
                print(f"{t['ticker']:<10} {t['confluence_score']:<8.0f} {t['signal']:<10} "
                      f"H:{t['hourly_appearances']:<3} "
                      f"D:{t['daily_appearances']:<3} "
                      f"{(t['hourly_momentum_avg'] + t['daily_momentum_avg'])/2:<10.2f}")
        
        # Emerging tickers
        print(f"\n🚀 EMERGING TICKERS (Strong Hourly, Not Yet Daily): {len(results['emerging_tickers'])}")
        print("-"*80)
        if results['emerging_tickers']:
            print(f"{'Ticker':<10} {'Strength':<10} {'Appearances':<15} {'Avg Mom':<10} {'Potential':<10}")
            print("-"*80)
            for t in results['emerging_tickers'][:10]:
                print(f"{t['ticker']:<10} {t['hourly_strength']:<10.0f} {t['hourly_appearances']:<15} "
                      f"{t['hourly_momentum_avg']:<10.2f} {t['potential']:<10}")
        
        # Alert candidates
        alerts = self.generate_alert_candidates(results)
        if alerts:
            print(f"\n🔔 ALERT CANDIDATES: {len(alerts)}")
            print("-"*80)
            for alert in alerts:
                print(f"[{alert['priority']}] {alert['message']}")
        
        print("\n" + "="*80)

def main():
    """Run confluence analysis"""
    analyzer = HourlyDailyConfluenceAnalyzer()
    results = analyzer.analyze_confluence()
    
    # Print analysis
    analyzer.print_analysis(results)
    
    # Save results
    output_file = os.path.join(analyzer.base_dir, 'analysis', 'hourly_daily_confluence.json')
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    # Generate alerts
    alerts = analyzer.generate_alert_candidates(results)
    if alerts:
        alerts_file = os.path.join(analyzer.base_dir, 'analysis', 'confluence_alerts.json')
        with open(alerts_file, 'w') as f:
            json.dump({'alerts': alerts, 'timestamp': datetime.datetime.now().isoformat()}, f, indent=2)
        print(f"Alerts saved to: {alerts_file}")

if __name__ == "__main__":
    main()