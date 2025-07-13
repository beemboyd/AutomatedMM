#!/usr/bin/env python
"""
Trend Weakness Analyzer - Based on Al Brooks Price Action
Analyzes portfolio positions for trend weakness patterns
"""

import os
import re
import json
import argparse
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from kiteconnect import KiteConnect
import configparser

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "trend_weakness_analyzer.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TrendWeaknessAnalyzer:
    def __init__(self, base_dir: str, user: str = "Sai"):
        self.base_dir = base_dir
        self.user = user
        self.logs_dir = os.path.join(base_dir, "logs")
        self.config = self.load_config()
        self.kite = self.initialize_kite()
        
        # Al Brooks trend weakness patterns scoring weights
        self.bull_weakness_weights = {
            'smaller_bull_bodies': 1,
            'top_tails_forming': 1,
            'top_tails_increasing': 2,
            'bar_overlap_increasing': 1,
            'small_body_or_doji': 2,
            'bear_body': 3,
            'high_at_or_below_prior': 2,
            'low_at_or_above_prior': 1,
            'low_below_prior': 2,
            'one_leg_pullback': 3,
            'two_leg_pullback': 4,
            'three_leg_pullback': 5,
            'minor_trendline_break': 3,
            'touch_ma': 2,
            'new_high_with_bear_bars': 4,
            'close_below_ma': 5,
            'high_below_ma': 6,
            'major_trendline_break': 7,
            'second_leg_down': 6,
            'multiple_pullbacks': 5,
            'larger_two_leg_pullback': 6,
            'trading_range_formed': 7,
            'false_breakout': 8
        }
        
        self.bear_weakness_weights = {
            'smaller_bear_bodies': 1,
            'bottom_tails_forming': 1,
            'bottom_tails_increasing': 2,
            'bar_overlap_increasing': 1,
            'small_body_or_doji': 2,
            'bull_body': 3,
            'low_at_or_above_prior': 2,
            'high_at_or_below_prior': 1,
            'high_above_prior': 2,
            'one_leg_pullback': 3,
            'two_leg_pullback': 4,
            'three_leg_pullback': 5,
            'minor_trendline_break': 3,
            'touch_ma': 2,
            'new_low_with_bull_bars': 4,
            'close_above_ma': 5,
            'low_above_ma': 6,
            'major_trendline_break': 7,
            'second_leg_up': 6,
            'multiple_pullbacks': 5,
            'larger_two_leg_pullback': 6,
            'trading_range_formed': 7,
            'false_breakout': 8
        }
        
    def load_config(self):
        """Load configuration from config.ini"""
        config_path = os.path.join(self.base_dir, 'config.ini')
        config = configparser.ConfigParser()
        config.read(config_path)
        return config
        
    def initialize_kite(self):
        """Initialize KiteConnect"""
        try:
            credential_section = f'API_CREDENTIALS_{self.user}'
            api_key = self.config.get(credential_section, 'api_key')
            access_token = self.config.get(credential_section, 'access_token')
            
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            return kite
        except Exception as e:
            logger.error(f"Failed to initialize KiteConnect: {e}")
            return None
            
    def get_portfolio_positions(self, user: str) -> Dict[str, Dict]:
        """Get current positions for a user from logs"""
        positions = {}
        log_file = os.path.join(self.logs_dir, user, f"SL_watchdog_{user}.log")
        
        if not os.path.exists(log_file):
            return positions
            
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                
            # Search for the most recent position data
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i]
                
                # Pattern: "🟢/🔴 TICKER: Qty=XXX, Avg=₹XXX.XX, LTP=₹XXX.XX"
                if ('🟢' in line or '🔴' in line) and 'Qty=' in line and 'Avg=₹' in line:
                    match = re.search(r'[🟢🔴]\s+(\w+):\s+Qty=(\d+),\s+Avg=₹([\d,]+\.?\d*),\s+LTP=₹([\d,]+\.?\d*)', line)
                    if match:
                        ticker = match.group(1)
                        if ticker not in positions:
                            positions[ticker] = {
                                'quantity': int(match.group(2)),
                                'avg_price': float(match.group(3).replace(',', '')),
                                'ltp': float(match.group(4).replace(',', ''))
                            }
                
                if len(positions) > 50:
                    break
                    
        except Exception as e:
            logger.error(f"Error parsing positions for {user}: {e}")
            
        return positions
        
    def fetch_ohlc_data(self, ticker: str, interval: str = 'day', days: int = 30) -> pd.DataFrame:
        """Fetch OHLC data for analysis"""
        try:
            # Get instrument token
            instruments = self.kite.instruments("NSE")
            instrument_df = pd.DataFrame(instruments)
            
            ticker_data = instrument_df[instrument_df['tradingsymbol'] == ticker]
            if ticker_data.empty:
                logger.warning(f"Instrument token not found for {ticker}")
                return pd.DataFrame()
                
            instrument_token = ticker_data.iloc[0]['instrument_token']
            
            # Fetch historical data
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            
            data = self.kite.historical_data(
                instrument_token,
                from_date.date(),
                to_date.date(),
                interval
            )
            
            if not data:
                return pd.DataFrame()
                
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            
            # Add derived columns for analysis
            df['body'] = df['close'] - df['open']
            df['body_size'] = abs(df['body'])
            df['range'] = df['high'] - df['low']
            df['body_percent'] = (df['body_size'] / df['range']) * 100
            df['upper_tail'] = df['high'] - df[['open', 'close']].max(axis=1)
            df['lower_tail'] = df[['open', 'close']].min(axis=1) - df['low']
            df['is_bull'] = df['body'] > 0
            df['is_bear'] = df['body'] < 0
            df['is_doji'] = df['body_percent'] < 10
            
            # Add moving average
            df['ma20'] = df['close'].rolling(window=20).mean()
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return pd.DataFrame()
            
    def detect_bull_trend_weakness(self, df: pd.DataFrame) -> Dict[str, bool]:
        """Detect bull trend weakness patterns"""
        patterns = {}
        
        if len(df) < 20:
            return patterns
            
        # Get recent bars for analysis
        recent = df.iloc[-10:]
        current = df.iloc[-1]
        prior = df.iloc[-2]
        
        # 1. Bull bodies becoming smaller
        recent_bull_bars = recent[recent['is_bull']]
        if len(recent_bull_bars) >= 3:
            body_sizes = recent_bull_bars['body_size'].values
            patterns['smaller_bull_bodies'] = all(body_sizes[i] <= body_sizes[i-1] 
                                                 for i in range(1, len(body_sizes)))
        
        # 2. Top tails forming
        patterns['top_tails_forming'] = current['upper_tail'] > current['body_size'] * 0.5
        
        # 3. Top tails increasing
        if len(recent) >= 3:
            tail_sizes = recent['upper_tail'].values[-3:]
            patterns['top_tails_increasing'] = all(tail_sizes[i] >= tail_sizes[i-1] 
                                                  for i in range(1, len(tail_sizes)))
        
        # 4. Bar overlap increasing
        patterns['bar_overlap_increasing'] = (
            min(current['high'], prior['high']) - max(current['low'], prior['low'])
        ) > df['range'].mean()
        
        # 5. Small body or doji
        patterns['small_body_or_doji'] = current['is_doji'] or current['body_percent'] < 20
        
        # 6. Bear body
        patterns['bear_body'] = current['is_bear']
        
        # 7. High at or below prior high
        patterns['high_at_or_below_prior'] = current['high'] <= prior['high']
        
        # 8. Low at or above prior low
        patterns['low_at_or_above_prior'] = current['low'] >= prior['low']
        
        # 9. Low below prior low
        patterns['low_below_prior'] = current['low'] < prior['low']
        
        # 10. One-legged pullback
        if len(recent) >= 2:
            patterns['one_leg_pullback'] = (recent['high'].iloc[-1] < recent['high'].iloc[-2])
        
        # 11. Two-legged pullback (5-10 bars)
        if len(recent) >= 5:
            highs = recent['high'].values
            pullback_count = sum(1 for i in range(1, len(highs)) if highs[i] < highs[i-1])
            patterns['two_leg_pullback'] = pullback_count >= 2
        
        # 12. Minor trendline break (simplified)
        if len(df) >= 10:
            recent_lows = df['low'].iloc[-10:].values
            trend_slope = np.polyfit(range(len(recent_lows)), recent_lows, 1)[0]
            patterns['minor_trendline_break'] = trend_slope < 0 and current['low'] < recent_lows[-3]
        
        # 13. Touch MA
        patterns['touch_ma'] = abs(current['low'] - current['ma20']) < current['range'] * 0.5
        
        # 14. Close below MA
        patterns['close_below_ma'] = current['close'] < current['ma20']
        
        # 15. High below MA
        patterns['high_below_ma'] = current['high'] < current['ma20']
        
        # 16. Trading range formed
        if len(recent) >= 5:
            price_range = recent['high'].max() - recent['low'].min()
            avg_range = df['range'].mean()
            patterns['trading_range_formed'] = price_range < avg_range * 5
        
        return patterns
        
    def detect_bear_trend_weakness(self, df: pd.DataFrame) -> Dict[str, bool]:
        """Detect bear trend weakness patterns"""
        patterns = {}
        
        if len(df) < 20:
            return patterns
            
        # Get recent bars for analysis
        recent = df.iloc[-10:]
        current = df.iloc[-1]
        prior = df.iloc[-2]
        
        # 1. Bear bodies becoming smaller
        recent_bear_bars = recent[recent['is_bear']]
        if len(recent_bear_bars) >= 3:
            body_sizes = recent_bear_bars['body_size'].values
            patterns['smaller_bear_bodies'] = all(body_sizes[i] <= body_sizes[i-1] 
                                                 for i in range(1, len(body_sizes)))
        
        # 2. Bottom tails forming
        patterns['bottom_tails_forming'] = current['lower_tail'] > current['body_size'] * 0.5
        
        # 3. Bottom tails increasing
        if len(recent) >= 3:
            tail_sizes = recent['lower_tail'].values[-3:]
            patterns['bottom_tails_increasing'] = all(tail_sizes[i] >= tail_sizes[i-1] 
                                                    for i in range(1, len(tail_sizes)))
        
        # 4. Bar overlap increasing
        patterns['bar_overlap_increasing'] = (
            min(current['high'], prior['high']) - max(current['low'], prior['low'])
        ) > df['range'].mean()
        
        # 5. Small body or doji
        patterns['small_body_or_doji'] = current['is_doji'] or current['body_percent'] < 20
        
        # 6. Bull body
        patterns['bull_body'] = current['is_bull']
        
        # 7. Low at or above prior low
        patterns['low_at_or_above_prior'] = current['low'] >= prior['low']
        
        # 8. High at or below prior high
        patterns['high_at_or_below_prior'] = current['high'] <= prior['high']
        
        # 9. High above prior high
        patterns['high_above_prior'] = current['high'] > prior['high']
        
        # 10. One-legged pullback
        if len(recent) >= 2:
            patterns['one_leg_pullback'] = (recent['low'].iloc[-1] > recent['low'].iloc[-2])
        
        # 11. Two-legged pullback (5-10 bars)
        if len(recent) >= 5:
            lows = recent['low'].values
            pullback_count = sum(1 for i in range(1, len(lows)) if lows[i] > lows[i-1])
            patterns['two_leg_pullback'] = pullback_count >= 2
        
        # 12. Minor trendline break (simplified)
        if len(df) >= 10:
            recent_highs = df['high'].iloc[-10:].values
            trend_slope = np.polyfit(range(len(recent_highs)), recent_highs, 1)[0]
            patterns['minor_trendline_break'] = trend_slope > 0 and current['high'] > recent_highs[-3]
        
        # 13. Touch MA
        patterns['touch_ma'] = abs(current['high'] - current['ma20']) < current['range'] * 0.5
        
        # 14. Close above MA
        patterns['close_above_ma'] = current['close'] > current['ma20']
        
        # 15. Low above MA
        patterns['low_above_ma'] = current['low'] > current['ma20']
        
        # 16. Trading range formed
        if len(recent) >= 5:
            price_range = recent['high'].max() - recent['low'].min()
            avg_range = df['range'].mean()
            patterns['trading_range_formed'] = price_range < avg_range * 5
        
        return patterns
        
    def calculate_weakness_score(self, patterns: Dict[str, bool], weights: Dict[str, int]) -> float:
        """Calculate weakness score based on detected patterns"""
        total_score = 0
        max_score = sum(weights.values())
        
        for pattern, detected in patterns.items():
            if detected and pattern in weights:
                total_score += weights[pattern]
                
        # Normalize to 0-100 scale
        return (total_score / max_score) * 100 if max_score > 0 else 0
        
    def determine_trend_direction(self, df: pd.DataFrame) -> str:
        """Determine if stock is in bull or bear trend"""
        if len(df) < 20:
            return "unknown"
            
        current_price = df['close'].iloc[-1]
        ma20 = df['ma20'].iloc[-1]
        
        # Simple trend determination
        if current_price > ma20:
            # Check if making higher highs and higher lows
            recent_highs = df['high'].iloc[-10:].values
            recent_lows = df['low'].iloc[-10:].values
            
            higher_highs = sum(1 for i in range(1, len(recent_highs)) 
                              if recent_highs[i] > recent_highs[i-1]) > 5
            higher_lows = sum(1 for i in range(1, len(recent_lows)) 
                             if recent_lows[i] > recent_lows[i-1]) > 5
            
            if higher_highs or higher_lows:
                return "bull"
        else:
            # Check if making lower highs and lower lows
            recent_highs = df['high'].iloc[-10:].values
            recent_lows = df['low'].iloc[-10:].values
            
            lower_highs = sum(1 for i in range(1, len(recent_highs)) 
                             if recent_highs[i] < recent_highs[i-1]) > 5
            lower_lows = sum(1 for i in range(1, len(recent_lows)) 
                            if recent_lows[i] < recent_lows[i-1]) > 5
            
            if lower_highs or lower_lows:
                return "bear"
                
        return "sideways"
        
    def analyze_position(self, ticker: str, position_data: Dict) -> Dict:
        """Analyze a single position for trend weakness"""
        result = {
            'ticker': ticker,
            'quantity': position_data['quantity'],
            'avg_price': position_data['avg_price'],
            'ltp': position_data['ltp'],
            'pnl_percent': ((position_data['ltp'] - position_data['avg_price']) / 
                           position_data['avg_price'] * 100),
            'trend': 'unknown',
            'weakness_score': 0,
            'detected_patterns': [],
            'recommendation': 'hold'
        }
        
        # Fetch OHLC data
        df = self.fetch_ohlc_data(ticker)
        if df.empty:
            logger.warning(f"No data available for {ticker}")
            return result
            
        # Determine trend direction
        trend = self.determine_trend_direction(df)
        result['trend'] = trend
        
        # Detect weakness patterns based on trend
        if trend == "bull":
            patterns = self.detect_bull_trend_weakness(df)
            score = self.calculate_weakness_score(patterns, self.bull_weakness_weights)
            result['weakness_score'] = score
            result['detected_patterns'] = [p for p, detected in patterns.items() if detected]
        elif trend == "bear":
            patterns = self.detect_bear_trend_weakness(df)
            score = self.calculate_weakness_score(patterns, self.bear_weakness_weights)
            result['weakness_score'] = score
            result['detected_patterns'] = [p for p, detected in patterns.items() if detected]
        else:
            result['weakness_score'] = 50  # Neutral for sideways
            
        # Generate recommendation based on score
        if result['weakness_score'] >= 70:
            result['recommendation'] = 'exit_immediately'
        elif result['weakness_score'] >= 50:
            result['recommendation'] = 'tighten_stop'
        elif result['weakness_score'] >= 30:
            result['recommendation'] = 'monitor_closely'
        else:
            result['recommendation'] = 'hold'
            
        return result
        
    def analyze_portfolio(self, user: str) -> List[Dict]:
        """Analyze entire portfolio for trend weakness"""
        logger.info(f"Analyzing portfolio for {user}")
        
        # Get positions
        positions = self.get_portfolio_positions(user)
        if not positions:
            logger.warning(f"No positions found for {user}")
            return []
            
        results = []
        for ticker, position_data in positions.items():
            logger.info(f"Analyzing {ticker}...")
            analysis = self.analyze_position(ticker, position_data)
            results.append(analysis)
            
        # Sort by weakness score (highest first)
        results.sort(key=lambda x: x['weakness_score'], reverse=True)
        
        return results
        
    def generate_report(self, all_user_results: Dict[str, List[Dict]]) -> None:
        """Generate trend weakness report"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print("\n" + "="*80)
        print(f"TREND WEAKNESS ANALYSIS REPORT - {timestamp}")
        print("="*80)
        print("Based on Al Brooks Price Action Patterns")
        print("="*80)
        
        for user, results in all_user_results.items():
            print(f"\n\n{'='*60}")
            print(f"USER: {user}")
            print(f"{'='*60}")
            
            if not results:
                print("No positions found")
                continue
                
            # Summary statistics
            total_positions = len(results)
            high_risk = sum(1 for r in results if r['weakness_score'] >= 70)
            medium_risk = sum(1 for r in results if 50 <= r['weakness_score'] < 70)
            low_risk = sum(1 for r in results if r['weakness_score'] < 50)
            
            print(f"\nPortfolio Summary:")
            print(f"Total Positions: {total_positions}")
            print(f"High Risk (Score ≥ 70): {high_risk}")
            print(f"Medium Risk (Score 50-69): {medium_risk}")
            print(f"Low Risk (Score < 50): {low_risk}")
            
            # Detailed analysis
            print(f"\n{'Ticker':<12} {'Trend':<8} {'Score':<8} {'P&L%':<10} {'Recommendation':<20} {'Key Patterns'}")
            print("-"*100)
            
            for result in results[:20]:  # Show top 20
                patterns_str = ', '.join(result['detected_patterns'][:3])
                if len(result['detected_patterns']) > 3:
                    patterns_str += f" (+{len(result['detected_patterns'])-3} more)"
                
                # Color code based on score
                if result['weakness_score'] >= 70:
                    symbol = "🔴"
                elif result['weakness_score'] >= 50:
                    symbol = "🟡"
                else:
                    symbol = "🟢"
                    
                print(f"{symbol} {result['ticker']:<10} {result['trend']:<8} "
                      f"{result['weakness_score']:<7.1f} {result['pnl_percent']:<9.2f} "
                      f"{result['recommendation']:<20} {patterns_str}")
            
            if len(results) > 20:
                print(f"\n... and {len(results) - 20} more positions")
        
        # Save detailed report
        self.save_detailed_report(all_user_results, timestamp)
        
    def save_detailed_report(self, all_user_results: Dict[str, List[Dict]], timestamp: str) -> None:
        """Save detailed report to Excel"""
        reports_dir = os.path.join(self.base_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        
        filename = os.path.join(reports_dir, 
                               f"trend_weakness_{timestamp.replace(':', '-').replace(' ', '_')}.xlsx")
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = []
            for user, results in all_user_results.items():
                if results:
                    summary_data.append({
                        'User': user,
                        'Total_Positions': len(results),
                        'Avg_Weakness_Score': np.mean([r['weakness_score'] for r in results]),
                        'High_Risk_Count': sum(1 for r in results if r['weakness_score'] >= 70),
                        'Exit_Recommendations': sum(1 for r in results 
                                                  if r['recommendation'] == 'exit_immediately')
                    })
            
            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Individual user sheets
            for user, results in all_user_results.items():
                if results:
                    user_df = pd.DataFrame(results)
                    # Convert list columns to string
                    user_df['detected_patterns'] = user_df['detected_patterns'].apply(
                        lambda x: ', '.join(x) if isinstance(x, list) else x
                    )
                    user_df.to_excel(writer, sheet_name=user, index=False)
        
        print(f"\nDetailed report saved to: {filename}")
        
    def run_analysis(self, users: List[str] = None) -> None:
        """Run trend weakness analysis for all users"""
        if users is None:
            users = ["Mom", "Sai", "Som", "Su"]
            
        all_results = {}
        
        for user in users:
            try:
                results = self.analyze_portfolio(user)
                all_results[user] = results
            except Exception as e:
                logger.error(f"Error analyzing portfolio for {user}: {e}")
                all_results[user] = []
                
        # Generate report
        self.generate_report(all_results)


def main():
    parser = argparse.ArgumentParser(
        description="Trend Weakness Analyzer based on Al Brooks patterns"
    )
    parser.add_argument("--base-dir", 
                       default="/Users/maverick/PycharmProjects/India-TS/Daily",
                       help="Base directory for India-TS Daily")
    parser.add_argument("--users", nargs="+", 
                       default=["Mom", "Sai", "Som", "Su"],
                       help="Users to analyze")
    parser.add_argument("--user", default="Sai",
                       help="User for API credentials")
    
    args = parser.parse_args()
    
    analyzer = TrendWeaknessAnalyzer(args.base_dir, args.user)
    analyzer.run_analysis(args.users)


if __name__ == "__main__":
    main()