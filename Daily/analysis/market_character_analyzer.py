#!/usr/bin/env python
"""
Market Character Change (CHoCH) Analyzer
Analyzes market-wide trend changes using multiple metrics from StrategyB reports
"""

import os
import glob
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
import matplotlib.pyplot as plt
import seaborn as sns
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "market_character_analyzer.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MarketCharacterAnalyzer:
    def __init__(self, base_dir: str, user: str = "Sai"):
        self.base_dir = base_dir
        self.user = user
        self.results_dir = os.path.join(base_dir, "results")
        self.config = self.load_config()
        self.kite = self.initialize_kite()
        
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
            
    def load_strategy_reports(self, days: int = 10) -> pd.DataFrame:
        """Load StrategyB reports from the last N days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        all_data = []
        
        pattern = os.path.join(self.results_dir, "StrategyB_Report_*.xlsx")
        files = sorted(glob.glob(pattern))
        
        for file in files:
            # Extract date from filename
            date_str = os.path.basename(file).replace("StrategyB_Report_", "").replace(".xlsx", "")
            try:
                file_date = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                if file_date < cutoff_date:
                    continue
                    
                # Load file
                df = pd.read_excel(file)
                df['report_date'] = file_date
                df['report_hour'] = file_date.hour
                all_data.append(df)
                
            except Exception as e:
                logger.warning(f"Error processing {file}: {e}")
                continue
                
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            logger.info(f"Loaded {len(all_data)} reports with {len(combined_df)} total entries")
            return combined_df
        else:
            logger.warning("No strategy reports found")
            return pd.DataFrame()
            
    def calculate_sma20_slopes(self, tickers: List[str], period: int = 5) -> Dict[str, float]:
        """Calculate SMA20 slopes for given tickers with rate limiting"""
        slopes = {}
        
        # Load instruments once
        try:
            instruments = self.kite.instruments("NSE")
            instrument_df = pd.DataFrame(instruments)
        except Exception as e:
            logger.error(f"Error loading instruments: {e}")
            return slopes
        
        # Process in batches with rate limiting
        batch_size = 20
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i+batch_size]
            
            for ticker in batch:
                try:
                    ticker_data = instrument_df[instrument_df['tradingsymbol'] == ticker]
                    
                    if ticker_data.empty:
                        continue
                        
                    instrument_token = ticker_data.iloc[0]['instrument_token']
                    
                    # Fetch historical data
                    to_date = datetime.now()
                    from_date = to_date - timedelta(days=30)
                    
                    data = self.kite.historical_data(
                        instrument_token,
                        from_date.date(),
                        to_date.date(),
                        'day'
                    )
                    
                    if not data or len(data) < 20:
                        continue
                        
                    df = pd.DataFrame(data)
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.set_index('date').sort_index()
                    
                    # Calculate SMA20
                    df['sma20'] = df['close'].rolling(window=20).mean()
                    
                    # Calculate slope over last N days
                    if len(df) >= 20 + period:
                        recent_sma = df['sma20'].iloc[-period:].values
                        x = np.arange(len(recent_sma))
                        slope = np.polyfit(x, recent_sma, 1)[0]
                        
                        # Normalize slope as percentage per day
                        avg_price = recent_sma.mean()
                        slope_pct = (slope / avg_price) * 100
                        slopes[ticker] = slope_pct
                        
                except Exception as e:
                    if "Too many requests" in str(e):
                        logger.warning(f"Rate limit hit, waiting 1 second...")
                        time.sleep(1)
                    else:
                        logger.error(f"Error calculating slope for {ticker}: {e}")
                    continue
            
            # Rate limiting between batches
            if i + batch_size < len(tickers):
                time.sleep(0.5)
                
        return slopes
        
    def analyze_market_breadth(self, df: pd.DataFrame) -> Dict:
        """Analyze market breadth indicators"""
        breadth = {}
        
        # Get unique tickers from recent reports
        recent_date = df['report_date'].max()
        recent_window = recent_date - timedelta(days=2)
        recent_df = df[df['report_date'] >= recent_window]
        
        unique_tickers = recent_df['Ticker'].unique().tolist()
        logger.info(f"Analyzing {len(unique_tickers)} unique tickers")
        
        # Calculate SMA20 slopes
        slopes = self.calculate_sma20_slopes(unique_tickers)
        
        if slopes:
            # Market breadth metrics
            breadth['total_tickers'] = len(slopes)
            breadth['positive_slopes'] = sum(1 for s in slopes.values() if s > 0)
            breadth['negative_slopes'] = sum(1 for s in slopes.values() if s < 0)
            breadth['positive_ratio'] = breadth['positive_slopes'] / breadth['total_tickers']
            breadth['avg_slope'] = np.mean(list(slopes.values()))
            breadth['median_slope'] = np.median(list(slopes.values()))
            
            # Strength distribution
            breadth['strong_uptrend'] = sum(1 for s in slopes.values() if s > 1.0)  # >1% per day
            breadth['weak_uptrend'] = sum(1 for s in slopes.values() if 0 < s <= 1.0)
            breadth['weak_downtrend'] = sum(1 for s in slopes.values() if -1.0 <= s < 0)
            breadth['strong_downtrend'] = sum(1 for s in slopes.values() if s < -1.0)
            
            # Store individual slopes for sector analysis
            breadth['ticker_slopes'] = slopes
            
        return breadth
        
    def analyze_pattern_distribution(self, df: pd.DataFrame) -> Dict:
        """Analyze distribution of patterns over time"""
        pattern_analysis = {}
        
        # Group by date and pattern
        date_pattern = df.groupby([df['report_date'].dt.date, 'Pattern']).size().reset_index(name='count')
        
        # Pivot to get patterns as columns
        pattern_pivot = date_pattern.pivot(index='report_date', columns='Pattern', values='count').fillna(0)
        
        # Calculate pattern trends
        pattern_analysis['pattern_counts'] = pattern_pivot.to_dict()
        
        # Analyze direction distribution
        direction_dist = df.groupby([df['report_date'].dt.date, 'Direction']).size().reset_index(name='count')
        direction_pivot = direction_dist.pivot(index='report_date', columns='Direction', values='count').fillna(0)
        
        if 'LONG' in direction_pivot.columns and 'SHORT' in direction_pivot.columns:
            direction_pivot['long_short_ratio'] = direction_pivot['LONG'] / (direction_pivot['SHORT'] + 1)
            pattern_analysis['avg_long_short_ratio'] = direction_pivot['long_short_ratio'].mean()
            pattern_analysis['recent_long_short_ratio'] = direction_pivot['long_short_ratio'].iloc[-1] if len(direction_pivot) > 0 else 0
        
        return pattern_analysis
        
    def analyze_sector_rotation(self, df: pd.DataFrame, slopes: Dict[str, float]) -> Dict:
        """Analyze sector rotation patterns"""
        sector_analysis = {}
        
        try:
            # Load sector data
            ticker_file = os.path.join(self.base_dir, "data", "Ticker_with_Sector.xlsx")
            if os.path.exists(ticker_file):
                sector_df = pd.read_excel(ticker_file)
                ticker_to_sector = dict(zip(sector_df['Ticker'], sector_df['Sector']))
                
                # Group slopes by sector
                sector_slopes = defaultdict(list)
                for ticker, slope in slopes.items():
                    sector = ticker_to_sector.get(ticker, 'Unknown')
                    sector_slopes[sector].append(slope)
                
                # Calculate sector averages
                sector_avgs = {}
                for sector, slopes_list in sector_slopes.items():
                    if slopes_list:
                        sector_avgs[sector] = {
                            'avg_slope': np.mean(slopes_list),
                            'median_slope': np.median(slopes_list),
                            'ticker_count': len(slopes_list),
                            'positive_count': sum(1 for s in slopes_list if s > 0)
                        }
                
                # Sort sectors by average slope
                sorted_sectors = sorted(sector_avgs.items(), 
                                      key=lambda x: x[1]['avg_slope'], 
                                      reverse=True)
                
                sector_analysis['top_sectors'] = sorted_sectors[:5]
                sector_analysis['bottom_sectors'] = sorted_sectors[-5:]
                sector_analysis['sector_details'] = sector_avgs
                
        except Exception as e:
            logger.error(f"Error in sector analysis: {e}")
            
        return sector_analysis
        
    def detect_character_change(self, breadth: Dict, pattern_dist: Dict) -> Dict:
        """Detect market character changes based on multiple indicators"""
        choch_signals = {
            'level': 'neutral',
            'signals': [],
            'strength': 0
        }
        
        # Check breadth indicators
        if breadth.get('positive_ratio', 0.5) < 0.3:
            choch_signals['signals'].append("Bearish breadth: <30% stocks in uptrend")
            choch_signals['strength'] -= 2
        elif breadth.get('positive_ratio', 0.5) > 0.7:
            choch_signals['signals'].append("Bullish breadth: >70% stocks in uptrend")
            choch_signals['strength'] += 2
            
        # Check average slope
        avg_slope = breadth.get('avg_slope', 0)
        if avg_slope < -0.5:
            choch_signals['signals'].append(f"Negative market slope: {avg_slope:.2f}%/day")
            choch_signals['strength'] -= 1
        elif avg_slope > 0.5:
            choch_signals['signals'].append(f"Positive market slope: {avg_slope:.2f}%/day")
            choch_signals['strength'] += 1
            
        # Check pattern distribution
        long_short_ratio = pattern_dist.get('recent_long_short_ratio', 1)
        if long_short_ratio < 0.5:
            choch_signals['signals'].append("Bearish pattern bias: More shorts than longs")
            choch_signals['strength'] -= 1
        elif long_short_ratio > 2:
            choch_signals['signals'].append("Bullish pattern bias: Longs dominate")
            choch_signals['strength'] += 1
            
        # Determine overall character
        if choch_signals['strength'] <= -3:
            choch_signals['level'] = 'strong_bearish'
        elif choch_signals['strength'] <= -1:
            choch_signals['level'] = 'bearish'
        elif choch_signals['strength'] >= 3:
            choch_signals['level'] = 'strong_bullish'
        elif choch_signals['strength'] >= 1:
            choch_signals['level'] = 'bullish'
            
        return choch_signals
        
    def generate_report(self, analysis_results: Dict) -> None:
        """Generate comprehensive market character report"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print("\n" + "="*80)
        print(f"MARKET CHARACTER ANALYSIS REPORT - {timestamp}")
        print("="*80)
        
        # Market Breadth
        breadth = analysis_results['breadth']
        print(f"\n📊 MARKET BREADTH ANALYSIS")
        print(f"{'='*40}")
        print(f"Total Tickers Analyzed: {breadth.get('total_tickers', 0)}")
        print(f"Positive Slopes: {breadth.get('positive_slopes', 0)} ({breadth.get('positive_ratio', 0)*100:.1f}%)")
        print(f"Negative Slopes: {breadth.get('negative_slopes', 0)} ({(1-breadth.get('positive_ratio', 0))*100:.1f}%)")
        print(f"Average Slope: {breadth.get('avg_slope', 0):.2f}% per day")
        print(f"Median Slope: {breadth.get('median_slope', 0):.2f}% per day")
        
        print(f"\n📈 TREND STRENGTH DISTRIBUTION")
        print(f"Strong Uptrend (>1%/day): {breadth.get('strong_uptrend', 0)}")
        print(f"Weak Uptrend (0-1%/day): {breadth.get('weak_uptrend', 0)}")
        print(f"Weak Downtrend (-1-0%/day): {breadth.get('weak_downtrend', 0)}")
        print(f"Strong Downtrend (<-1%/day): {breadth.get('strong_downtrend', 0)}")
        
        # Pattern Distribution
        pattern_dist = analysis_results['pattern_distribution']
        print(f"\n🎯 PATTERN ANALYSIS")
        print(f"{'='*40}")
        print(f"Avg Long/Short Ratio: {pattern_dist.get('avg_long_short_ratio', 0):.2f}")
        print(f"Recent Long/Short Ratio: {pattern_dist.get('recent_long_short_ratio', 0):.2f}")
        
        # Sector Rotation
        sector = analysis_results.get('sector_rotation', {})
        if sector and sector.get('top_sectors'):
            print(f"\n🔄 SECTOR ROTATION")
            print(f"{'='*40}")
            print("Top 5 Sectors:")
            for sector_name, data in sector['top_sectors']:
                print(f"  {sector_name}: {data['avg_slope']:.2f}%/day ({data['ticker_count']} stocks)")
            
            print("\nBottom 5 Sectors:")
            for sector_name, data in sector.get('bottom_sectors', []):
                print(f"  {sector_name}: {data['avg_slope']:.2f}%/day ({data['ticker_count']} stocks)")
        
        # Character Change Detection
        choch = analysis_results.get('character_change', {})
        if choch:
            print(f"\n🔍 MARKET CHARACTER ASSESSMENT")
            print(f"{'='*40}")
            print(f"Overall Character: {choch['level'].upper()}")
            print(f"Signal Strength: {choch['strength']}")
            print("\nKey Signals:")
            for signal in choch['signals']:
                print(f"  • {signal}")
            
        # Save detailed report
        self.save_detailed_report(analysis_results)
        
    def save_detailed_report(self, analysis_results: Dict) -> None:
        """Save detailed analysis to Excel"""
        reports_dir = os.path.join(self.base_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = os.path.join(reports_dir, f"market_character_{timestamp}.xlsx")
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = {
                'Metric': ['Total Tickers', 'Positive Ratio', 'Average Slope', 
                          'Market Character', 'Signal Strength'],
                'Value': [
                    analysis_results['breadth'].get('total_tickers', 0),
                    f"{analysis_results['breadth'].get('positive_ratio', 0)*100:.1f}%",
                    f"{analysis_results['breadth'].get('avg_slope', 0):.2f}%",
                    analysis_results['character_change']['level'],
                    analysis_results['character_change']['strength']
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Ticker slopes sheet
            if 'ticker_slopes' in analysis_results['breadth']:
                slopes_df = pd.DataFrame(
                    list(analysis_results['breadth']['ticker_slopes'].items()),
                    columns=['Ticker', 'SMA20_Slope_%_per_day']
                ).sort_values('SMA20_Slope_%_per_day', ascending=False)
                slopes_df.to_excel(writer, sheet_name='Ticker_Slopes', index=False)
            
            # Sector analysis sheet
            if 'sector_rotation' in analysis_results and 'sector_details' in analysis_results['sector_rotation']:
                sector_data = []
                for sector, data in analysis_results['sector_rotation']['sector_details'].items():
                    sector_data.append({
                        'Sector': sector,
                        'Avg_Slope': data['avg_slope'],
                        'Median_Slope': data['median_slope'],
                        'Ticker_Count': data['ticker_count'],
                        'Positive_Count': data['positive_count']
                    })
                sector_df = pd.DataFrame(sector_data).sort_values('Avg_Slope', ascending=False)
                sector_df.to_excel(writer, sheet_name='Sector_Analysis', index=False)
                
        print(f"\nDetailed report saved to: {filename}")
        
        # Generate visualization
        self.create_visualization(analysis_results, timestamp)
        
    def create_visualization(self, analysis_results: Dict, timestamp: str) -> None:
        """Create market character visualization"""
        try:
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            fig.suptitle(f'Market Character Analysis - {timestamp}', fontsize=16)
            
            # 1. Slope distribution histogram
            if 'ticker_slopes' in analysis_results['breadth']:
                slopes = list(analysis_results['breadth']['ticker_slopes'].values())
                axes[0, 0].hist(slopes, bins=30, edgecolor='black', alpha=0.7)
                axes[0, 0].axvline(x=0, color='red', linestyle='--', label='Zero line')
                axes[0, 0].set_title('SMA20 Slope Distribution')
                axes[0, 0].set_xlabel('Slope (% per day)')
                axes[0, 0].set_ylabel('Count')
                axes[0, 0].legend()
            
            # 2. Trend strength pie chart
            breadth = analysis_results['breadth']
            sizes = [
                breadth.get('strong_uptrend', 0),
                breadth.get('weak_uptrend', 0),
                breadth.get('weak_downtrend', 0),
                breadth.get('strong_downtrend', 0)
            ]
            labels = ['Strong Up', 'Weak Up', 'Weak Down', 'Strong Down']
            colors = ['darkgreen', 'lightgreen', 'orange', 'red']
            axes[0, 1].pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%')
            axes[0, 1].set_title('Trend Strength Distribution')
            
            # 3. Top sectors bar chart
            if 'sector_rotation' in analysis_results and 'top_sectors' in analysis_results['sector_rotation']:
                sectors = [s[0][:15] for s in analysis_results['sector_rotation']['top_sectors']]
                slopes = [s[1]['avg_slope'] for s in analysis_results['sector_rotation']['top_sectors']]
                axes[1, 0].bar(sectors, slopes, color='green', alpha=0.7)
                axes[1, 0].set_title('Top 5 Sectors by Slope')
                axes[1, 0].set_xlabel('Sector')
                axes[1, 0].set_ylabel('Avg Slope (% per day)')
                axes[1, 0].tick_params(axis='x', rotation=45)
            
            # 4. Market character gauge
            ax = axes[1, 1]
            strength = analysis_results.get('character_change', {}).get('strength', 0)
            character_level = analysis_results.get('character_change', {}).get('level', 'neutral')
            max_strength = 5
            
            # Create gauge
            theta = np.linspace(0, np.pi, 100)
            r_inner = 0.7
            r_outer = 1.0
            
            # Color segments
            colors_gauge = ['red', 'orange', 'yellow', 'lightgreen', 'green']
            n_segments = len(colors_gauge)
            
            for i in range(n_segments):
                theta_start = i * np.pi / n_segments
                theta_end = (i + 1) * np.pi / n_segments
                theta_seg = np.linspace(theta_start, theta_end, 20)
                
                x_inner = r_inner * np.cos(theta_seg)
                y_inner = r_inner * np.sin(theta_seg)
                x_outer = r_outer * np.cos(theta_seg)
                y_outer = r_outer * np.sin(theta_seg)
                
                x = np.concatenate([x_inner, x_outer[::-1]])
                y = np.concatenate([y_inner, y_outer[::-1]])
                
                ax.fill(x, y, color=colors_gauge[i], alpha=0.3)
            
            # Add needle
            angle = (strength + max_strength) / (2 * max_strength) * np.pi
            ax.plot([0, 0.8 * np.cos(angle)], [0, 0.8 * np.sin(angle)], 
                   'k-', linewidth=3)
            ax.plot(0, 0, 'ko', markersize=10)
            
            ax.set_xlim(-1.2, 1.2)
            ax.set_ylim(-0.2, 1.2)
            ax.set_aspect('equal')
            ax.axis('off')
            ax.set_title(f"Market Character: {character_level.upper()}")
            
            plt.tight_layout()
            
            # Save plot
            plot_filename = os.path.join(self.base_dir, "reports", 
                                       f"market_character_plot_{timestamp.replace(':', '-')}.png")
            plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"Visualization saved to: {plot_filename}")
            
        except Exception as e:
            logger.error(f"Error creating visualization: {e}")
            
    def run_analysis(self, days: int = 10) -> Dict:
        """Run complete market character analysis"""
        logger.info(f"Starting market character analysis for last {days} days")
        
        # Load strategy reports
        df = self.load_strategy_reports(days)
        if df.empty:
            logger.error("No data to analyze")
            return {}
            
        # Run analyses
        analysis_results = {
            'breadth': self.analyze_market_breadth(df),
            'pattern_distribution': self.analyze_pattern_distribution(df),
            'data_summary': {
                'total_reports': df['report_date'].nunique(),
                'total_entries': len(df),
                'date_range': f"{df['report_date'].min()} to {df['report_date'].max()}"
            }
        }
        
        # Add sector rotation if slopes available
        if 'ticker_slopes' in analysis_results['breadth']:
            analysis_results['sector_rotation'] = self.analyze_sector_rotation(
                df, analysis_results['breadth']['ticker_slopes']
            )
        
        # Detect character changes
        analysis_results['character_change'] = self.detect_character_change(
            analysis_results['breadth'],
            analysis_results['pattern_distribution']
        )
        
        # Generate report
        self.generate_report(analysis_results)
        
        return analysis_results


def main():
    parser = argparse.ArgumentParser(
        description="Market Character Change (CHoCH) Analyzer"
    )
    parser.add_argument("--base-dir", 
                       default="/Users/maverick/PycharmProjects/India-TS/Daily",
                       help="Base directory for India-TS Daily")
    parser.add_argument("--days", type=int, default=10,
                       help="Number of days to analyze")
    parser.add_argument("--user", default="Sai",
                       help="User for API credentials")
    
    args = parser.parse_args()
    
    analyzer = MarketCharacterAnalyzer(args.base_dir, args.user)
    analyzer.run_analysis(args.days)


if __name__ == "__main__":
    main()