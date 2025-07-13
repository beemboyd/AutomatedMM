#!/usr/bin/env python
"""
Market Character Change (CHoCH) Analyzer - Simple Version
Analyzes market-wide trend changes using StrategyB reports without API calls
"""

import os
import glob
import argparse
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

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
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.results_dir = os.path.join(base_dir, "results")
        self.data_dir = os.path.join(base_dir, "data")
        
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
                df['report_day'] = file_date.date()
                
                # Clean numeric columns
                if 'Momentum_5D' in df.columns:
                    df['Momentum_5D'] = pd.to_numeric(df['Momentum_5D'], errors='coerce').fillna(0)
                if 'Volume_Ratio' in df.columns:
                    df['Volume_Ratio'] = pd.to_numeric(df['Volume_Ratio'], errors='coerce').fillna(1)
                if 'Score' in df.columns:
                    df['Score'] = pd.to_numeric(df['Score'], errors='coerce').fillna(0)
                    
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
            
    def analyze_ticker_trends(self, df: pd.DataFrame) -> Dict:
        """Analyze ticker appearance frequency and momentum trends"""
        trends = {}
        
        # Group by day and ticker
        daily_tickers = df.groupby(['report_day', 'Ticker']).agg({
            'Score': 'mean',
            'Direction': lambda x: x.mode()[0] if len(x) > 0 else 'UNKNOWN',
            'Momentum_5D': 'mean',
            'Volume_Ratio': 'mean'
        }).reset_index()
        
        # Calculate ticker frequency (how often each ticker appears)
        ticker_freq = df.groupby('Ticker').agg({
            'report_date': 'count',
            'Direction': lambda x: (x == 'LONG').sum() / len(x),  # Long bias
            'Score': 'mean',
            'Momentum_5D': 'mean'
        }).rename(columns={
            'report_date': 'appearance_count',
            'Direction': 'long_bias'
        })
        
        # Identify trending tickers (appearing frequently with consistent direction)
        trending_up = ticker_freq[
            (ticker_freq['appearance_count'] >= 3) & 
            (ticker_freq['long_bias'] >= 0.8) &
            (ticker_freq['Momentum_5D'] > 0)
        ].sort_values('Momentum_5D', ascending=False)
        
        trending_down = ticker_freq[
            (ticker_freq['appearance_count'] >= 3) & 
            (ticker_freq['long_bias'] <= 0.2) &
            (ticker_freq['Momentum_5D'] < 0)
        ].sort_values('Momentum_5D')
        
        trends['ticker_frequency'] = ticker_freq
        trends['trending_up'] = trending_up
        trends['trending_down'] = trending_down
        trends['total_unique_tickers'] = len(ticker_freq)
        trends['strong_uptrend_count'] = len(trending_up)
        trends['strong_downtrend_count'] = len(trending_down)
        
        return trends
        
    def analyze_pattern_distribution(self, df: pd.DataFrame) -> Dict:
        """Analyze distribution of patterns over time"""
        pattern_analysis = {}
        
        # Group by date and pattern
        date_pattern = df.groupby([df['report_date'].dt.date, 'Pattern']).size().reset_index(name='count')
        
        # Get pattern frequency
        pattern_freq = df['Pattern'].value_counts().to_dict()
        pattern_analysis['pattern_frequency'] = pattern_freq
        
        # Analyze direction distribution over time
        direction_by_day = df.groupby(['report_day', 'Direction']).size().unstack(fill_value=0)
        
        if 'LONG' in direction_by_day.columns and 'SHORT' in direction_by_day.columns:
            direction_by_day['long_short_ratio'] = direction_by_day['LONG'] / (direction_by_day['SHORT'] + 1)
            pattern_analysis['daily_long_short_ratio'] = direction_by_day['long_short_ratio'].to_dict()
            pattern_analysis['avg_long_short_ratio'] = direction_by_day['long_short_ratio'].mean()
            pattern_analysis['recent_long_short_ratio'] = direction_by_day['long_short_ratio'].iloc[-1] if len(direction_by_day) > 0 else 1
            
            # Trend in long/short ratio
            if len(direction_by_day) >= 3:
                recent_ratios = direction_by_day['long_short_ratio'].iloc[-3:].values
                pattern_analysis['ratio_trend'] = 'increasing' if recent_ratios[-1] > recent_ratios[0] else 'decreasing'
            else:
                pattern_analysis['ratio_trend'] = 'stable'
        
        # Momentum analysis
        avg_momentum_by_day = df.groupby('report_day')['Momentum_5D'].mean()
        pattern_analysis['daily_avg_momentum'] = avg_momentum_by_day.to_dict()
        pattern_analysis['overall_avg_momentum'] = df['Momentum_5D'].mean()
        pattern_analysis['recent_avg_momentum'] = avg_momentum_by_day.iloc[-1] if len(avg_momentum_by_day) > 0 else 0
        
        return pattern_analysis
        
    def analyze_sector_distribution(self, df: pd.DataFrame) -> Dict:
        """Analyze sector distribution without API calls"""
        sector_analysis = {}
        
        try:
            # Load sector data
            ticker_file = os.path.join(self.data_dir, "Ticker_with_Sector.xlsx")
            if os.path.exists(ticker_file):
                sector_df = pd.read_excel(ticker_file)
                ticker_to_sector = dict(zip(sector_df['Ticker'], sector_df['Sector']))
                
                # Add sector to main dataframe
                df['Sector'] = df['Ticker'].map(ticker_to_sector).fillna('Unknown')
                
                # Sector frequency
                sector_freq = df.groupby('Sector').agg({
                    'Ticker': 'count',
                    'Direction': lambda x: (x == 'LONG').sum() / len(x),
                    'Momentum_5D': 'mean',
                    'Score': 'mean'
                }).rename(columns={
                    'Ticker': 'appearance_count',
                    'Direction': 'long_bias'
                }).sort_values('appearance_count', ascending=False)
                
                # Top performing sectors by momentum
                top_momentum_sectors = sector_freq.sort_values('Momentum_5D', ascending=False).head(5)
                bottom_momentum_sectors = sector_freq.sort_values('Momentum_5D').head(5)
                
                # Sector rotation - compare recent vs overall
                recent_date = df['report_date'].max() - timedelta(days=2)
                recent_sector_dist = df[df['report_date'] >= recent_date].groupby('Sector').size()
                overall_sector_dist = df.groupby('Sector').size()
                
                sector_rotation = {}
                for sector in sector_freq.index:
                    recent_pct = recent_sector_dist.get(sector, 0) / len(df[df['report_date'] >= recent_date])
                    overall_pct = overall_sector_dist.get(sector, 0) / len(df)
                    sector_rotation[sector] = {
                        'recent_pct': recent_pct,
                        'overall_pct': overall_pct,
                        'change': recent_pct - overall_pct
                    }
                
                # Sort by change to identify rotating sectors
                rotating_in = sorted([(s, d['change']) for s, d in sector_rotation.items() if d['change'] > 0], 
                                   key=lambda x: x[1], reverse=True)[:5]
                rotating_out = sorted([(s, d['change']) for s, d in sector_rotation.items() if d['change'] < 0], 
                                    key=lambda x: x[1])[:5]
                
                sector_analysis['sector_frequency'] = sector_freq
                sector_analysis['top_momentum_sectors'] = top_momentum_sectors
                sector_analysis['bottom_momentum_sectors'] = bottom_momentum_sectors
                sector_analysis['rotating_in'] = rotating_in
                sector_analysis['rotating_out'] = rotating_out
                
        except Exception as e:
            logger.error(f"Error in sector analysis: {e}")
            
        return sector_analysis
        
    def detect_character_change(self, trends: Dict, patterns: Dict, sectors: Dict) -> Dict:
        """Detect market character changes based on multiple indicators"""
        choch_signals = {
            'level': 'neutral',
            'signals': [],
            'strength': 0
        }
        
        # Check trend balance
        up_count = trends.get('strong_uptrend_count', 0)
        down_count = trends.get('strong_downtrend_count', 0)
        total_tickers = trends.get('total_unique_tickers', 1)
        
        if up_count > down_count * 2:
            choch_signals['signals'].append(f"Bullish ticker bias: {up_count} strong uptrends vs {down_count} downtrends")
            choch_signals['strength'] += 2
        elif down_count > up_count * 2:
            choch_signals['signals'].append(f"Bearish ticker bias: {down_count} strong downtrends vs {up_count} uptrends")
            choch_signals['strength'] -= 2
            
        # Check pattern distribution
        long_short_ratio = patterns.get('recent_long_short_ratio', 1)
        ratio_trend = patterns.get('ratio_trend', 'stable')
        
        if long_short_ratio < 0.5:
            choch_signals['signals'].append(f"Bearish pattern bias: L/S ratio = {long_short_ratio:.2f}")
            choch_signals['strength'] -= 1
        elif long_short_ratio > 2:
            choch_signals['signals'].append(f"Bullish pattern bias: L/S ratio = {long_short_ratio:.2f}")
            choch_signals['strength'] += 1
            
        if ratio_trend == 'decreasing':
            choch_signals['signals'].append("Long/Short ratio trending down")
            choch_signals['strength'] -= 1
        elif ratio_trend == 'increasing':
            choch_signals['signals'].append("Long/Short ratio trending up")
            choch_signals['strength'] += 1
            
        # Check momentum
        recent_momentum = patterns.get('recent_avg_momentum', 0)
        overall_momentum = patterns.get('overall_avg_momentum', 0)
        
        if recent_momentum < overall_momentum - 2:
            choch_signals['signals'].append(f"Momentum weakening: {recent_momentum:.2f}% vs {overall_momentum:.2f}% avg")
            choch_signals['strength'] -= 1
        elif recent_momentum > overall_momentum + 2:
            choch_signals['signals'].append(f"Momentum strengthening: {recent_momentum:.2f}% vs {overall_momentum:.2f}% avg")
            choch_signals['strength'] += 1
            
        # Check sector rotation
        if sectors and 'rotating_in' in sectors:
            if len(sectors['rotating_in']) > 0:
                top_rotating_in = sectors['rotating_in'][0]
                choch_signals['signals'].append(f"Sector rotating in: {top_rotating_in[0]} (+{top_rotating_in[1]*100:.1f}%)")
                
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
        
        # Data Summary
        data_summary = analysis_results.get('data_summary', {})
        print(f"\n📊 DATA SUMMARY")
        print(f"{'='*40}")
        print(f"Reports Analyzed: {data_summary.get('total_reports', 0)}")
        print(f"Total Entries: {data_summary.get('total_entries', 0)}")
        print(f"Date Range: {data_summary.get('date_range', 'N/A')}")
        
        # Ticker Trends
        trends = analysis_results.get('ticker_trends', {})
        print(f"\n📈 TICKER TREND ANALYSIS")
        print(f"{'='*40}")
        print(f"Unique Tickers: {trends.get('total_unique_tickers', 0)}")
        print(f"Strong Uptrends: {trends.get('strong_uptrend_count', 0)}")
        print(f"Strong Downtrends: {trends.get('strong_downtrend_count', 0)}")
        
        if 'trending_up' in trends and len(trends['trending_up']) > 0:
            print("\nTop 5 Trending Up:")
            for ticker, data in trends['trending_up'].head(5).iterrows():
                print(f"  {ticker}: {data['Momentum_5D']:.2f}% momentum, {data['appearance_count']} appearances")
        
        # Pattern Distribution
        patterns = analysis_results.get('pattern_distribution', {})
        print(f"\n🎯 PATTERN ANALYSIS")
        print(f"{'='*40}")
        print(f"Avg Long/Short Ratio: {patterns.get('avg_long_short_ratio', 0):.2f}")
        print(f"Recent Long/Short Ratio: {patterns.get('recent_long_short_ratio', 0):.2f}")
        print(f"Ratio Trend: {patterns.get('ratio_trend', 'stable')}")
        print(f"Overall Avg Momentum: {patterns.get('overall_avg_momentum', 0):.2f}%")
        print(f"Recent Avg Momentum: {patterns.get('recent_avg_momentum', 0):.2f}%")
        
        # Sector Analysis
        sectors = analysis_results.get('sector_distribution', {})
        if sectors and 'top_momentum_sectors' in sectors:
            print(f"\n🔄 SECTOR ANALYSIS")
            print(f"{'='*40}")
            print("Top Momentum Sectors:")
            for sector, data in sectors['top_momentum_sectors'].iterrows():
                print(f"  {sector}: {data['Momentum_5D']:.2f}% avg momentum")
                
            if 'rotating_in' in sectors and sectors['rotating_in']:
                print("\nSectors Rotating In:")
                for sector, change in sectors['rotating_in'][:3]:
                    print(f"  {sector}: +{change*100:.1f}% change")
        
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
        filename = os.path.join(reports_dir, f"market_character_simple_{timestamp}.xlsx")
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = {
                'Metric': ['Total Reports', 'Unique Tickers', 'Strong Uptrends', 'Strong Downtrends',
                          'Avg L/S Ratio', 'Recent L/S Ratio', 'Market Character', 'Signal Strength'],
                'Value': [
                    analysis_results.get('data_summary', {}).get('total_reports', 0),
                    analysis_results.get('ticker_trends', {}).get('total_unique_tickers', 0),
                    analysis_results.get('ticker_trends', {}).get('strong_uptrend_count', 0),
                    analysis_results.get('ticker_trends', {}).get('strong_downtrend_count', 0),
                    f"{analysis_results.get('pattern_distribution', {}).get('avg_long_short_ratio', 0):.2f}",
                    f"{analysis_results.get('pattern_distribution', {}).get('recent_long_short_ratio', 0):.2f}",
                    analysis_results.get('character_change', {}).get('level', 'neutral'),
                    analysis_results.get('character_change', {}).get('strength', 0)
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Ticker trends
            if 'ticker_trends' in analysis_results and 'ticker_frequency' in analysis_results['ticker_trends']:
                ticker_df = analysis_results['ticker_trends']['ticker_frequency']
                ticker_df.to_excel(writer, sheet_name='Ticker_Analysis')
                
            # Sector analysis
            if 'sector_distribution' in analysis_results and 'sector_frequency' in analysis_results['sector_distribution']:
                sector_df = analysis_results['sector_distribution']['sector_frequency']
                sector_df.to_excel(writer, sheet_name='Sector_Analysis')
                
        print(f"\nDetailed report saved to: {filename}")
        
        # Generate visualization
        self.create_visualization(analysis_results, timestamp)
        
    def create_visualization(self, analysis_results: Dict, timestamp: str) -> None:
        """Create market character visualization"""
        try:
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            fig.suptitle(f'Market Character Analysis - {timestamp}', fontsize=16)
            
            # 1. Long/Short ratio over time
            patterns = analysis_results.get('pattern_distribution', {})
            if 'daily_long_short_ratio' in patterns:
                dates = list(patterns['daily_long_short_ratio'].keys())
                ratios = list(patterns['daily_long_short_ratio'].values())
                axes[0, 0].plot(dates, ratios, marker='o')
                axes[0, 0].axhline(y=1, color='r', linestyle='--', alpha=0.5)
                axes[0, 0].set_title('Long/Short Ratio Trend')
                axes[0, 0].set_xlabel('Date')
                axes[0, 0].set_ylabel('L/S Ratio')
                axes[0, 0].tick_params(axis='x', rotation=45)
            
            # 2. Momentum distribution
            if 'daily_avg_momentum' in patterns:
                dates = list(patterns['daily_avg_momentum'].keys())
                momentum = list(patterns['daily_avg_momentum'].values())
                axes[0, 1].bar(dates, momentum, alpha=0.7, 
                              color=['green' if m > 0 else 'red' for m in momentum])
                axes[0, 1].axhline(y=0, color='black', linestyle='-', alpha=0.5)
                axes[0, 1].set_title('Daily Average Momentum')
                axes[0, 1].set_xlabel('Date')
                axes[0, 1].set_ylabel('Avg Momentum %')
                axes[0, 1].tick_params(axis='x', rotation=45)
            
            # 3. Sector momentum
            sectors = analysis_results.get('sector_distribution', {})
            if 'top_momentum_sectors' in sectors:
                sector_names = sectors['top_momentum_sectors'].index[:10]
                sector_momentum = sectors['top_momentum_sectors']['Momentum_5D'].values[:10]
                axes[1, 0].barh(sector_names, sector_momentum, 
                               color=['green' if m > 0 else 'red' for m in sector_momentum])
                axes[1, 0].set_title('Top 10 Sectors by Momentum')
                axes[1, 0].set_xlabel('Avg Momentum %')
            
            # 4. Market character summary
            ax = axes[1, 1]
            ax.text(0.5, 0.7, 'Market Character', ha='center', va='center', 
                   fontsize=16, weight='bold')
            
            choch = analysis_results.get('character_change', {})
            character = choch.get('level', 'neutral').upper()
            strength = choch.get('strength', 0)
            
            # Color based on character
            colors_map = {
                'STRONG_BEARISH': 'darkred',
                'BEARISH': 'red',
                'NEUTRAL': 'gray',
                'BULLISH': 'green',
                'STRONG_BULLISH': 'darkgreen'
            }
            color = colors_map.get(character, 'gray')
            
            ax.text(0.5, 0.5, character, ha='center', va='center', 
                   fontsize=24, weight='bold', color=color)
            ax.text(0.5, 0.3, f'Strength: {strength}', ha='center', va='center', 
                   fontsize=14)
            
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            
            plt.tight_layout()
            
            # Save plot
            plot_filename = os.path.join(self.base_dir, "reports", 
                                       f"market_character_simple_plot_{timestamp.replace(':', '-')}.png")
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
            'ticker_trends': self.analyze_ticker_trends(df),
            'pattern_distribution': self.analyze_pattern_distribution(df),
            'sector_distribution': self.analyze_sector_distribution(df),
            'data_summary': {
                'total_reports': df['report_date'].nunique(),
                'total_entries': len(df),
                'date_range': f"{df['report_date'].min()} to {df['report_date'].max()}"
            }
        }
        
        # Detect character changes
        analysis_results['character_change'] = self.detect_character_change(
            analysis_results['ticker_trends'],
            analysis_results['pattern_distribution'],
            analysis_results['sector_distribution']
        )
        
        # Generate report
        self.generate_report(analysis_results)
        
        return analysis_results


def main():
    parser = argparse.ArgumentParser(
        description="Market Character Change (CHoCH) Analyzer - Simple Version"
    )
    parser.add_argument("--base-dir", 
                       default="/Users/maverick/PycharmProjects/India-TS/Daily",
                       help="Base directory for India-TS Daily")
    parser.add_argument("--days", type=int, default=None,
                       help="Number of days to analyze")
    
    args = parser.parse_args()
    
    # If days not provided via command line, ask user
    if args.days is None:
        while True:
            try:
                days_input = input("\nEnter the number of days to analyze (default: 10): ").strip()
                if not days_input:
                    days = 10
                    print(f"Using default: {days} days")
                    break
                days = int(days_input)
                if days <= 0:
                    print("Please enter a positive number of days.")
                    continue
                if days > 365:
                    confirm = input(f"Analyzing {days} days may take a while. Continue? (y/n): ").strip().lower()
                    if confirm != 'y':
                        continue
                break
            except ValueError:
                print("Please enter a valid number.")
                continue
    else:
        days = args.days
    
    analyzer = MarketCharacterAnalyzer(args.base_dir)
    analyzer.run_analysis(days)


if __name__ == "__main__":
    main()