#!/usr/bin/env python3
"""
Market Condition Analyzer for Brooks Strategy Performance

This script analyzes overall market conditions during periods when Brooks strategies
performed well, helping identify similar conditions for future strategy deployment.

Author: AI Assistant
Date: 2025-05-24
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MarketConditionAnalyzer:
    def __init__(self):
        """Initialize the Market Condition Analyzer"""
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.script_dir)
        self.data_dir = os.path.join(self.project_root, "Daily", "data")
        self.ohlc_dir = os.path.join(self.script_dir, "data", "ohlc_data", "daily")
        self.ticker_file = os.path.join(self.data_dir, "Ticker.xlsx")
        
        logger.info("Initialized Market Condition Analyzer")
        logger.info(f"OHLC data directory: {self.ohlc_dir}")
        logger.info(f"Ticker file: {self.ticker_file}")
    
    def load_ticker_universe(self):
        """Load all tickers from Ticker.xlsx"""
        try:
            df = pd.read_excel(self.ticker_file)
            
            # Try different column names for tickers
            ticker_columns = ['Ticker', 'Symbol', 'SYMBOL', 'ticker', 'symbol', 'Script', 'SCRIPT']
            ticker_column = None
            
            for col in ticker_columns:
                if col in df.columns:
                    ticker_column = col
                    break
            
            if ticker_column is None:
                # Use first column
                ticker_column = df.columns[0]
                logger.warning(f"Using first column '{ticker_column}' as ticker column")
            
            tickers = df[ticker_column].dropna().astype(str).str.strip().tolist()
            logger.info(f"Loaded {len(tickers)} tickers from universe")
            return tickers
            
        except Exception as e:
            logger.error(f"Error loading ticker universe: {e}")
            return []
    
    def load_ohlc_data_for_period(self, tickers, start_date, end_date):
        """Load OHLC data for all tickers in the specified period"""
        market_data = {}
        successful_loads = 0
        
        for ticker in tickers:
            try:
                file_path = os.path.join(self.ohlc_dir, f"{ticker}_day.csv")
                
                if os.path.exists(file_path):
                    df = pd.read_csv(file_path)
                    df['date'] = pd.to_datetime(df['date'])

                    # Filter for the specified period (compare just the date part)
                    mask = (df['date'].dt.date >= start_date.date()) & (df['date'].dt.date <= end_date.date())
                    period_data = df[mask].copy()
                    
                    if len(period_data) > 0:
                        market_data[ticker] = period_data
                        successful_loads += 1
                
            except Exception as e:
                logger.debug(f"Could not load data for {ticker}: {e}")
                continue
        
        logger.info(f"Successfully loaded data for {successful_loads}/{len(tickers)} tickers")
        return market_data
    
    def calculate_market_metrics(self, market_data):
        """Calculate comprehensive market condition metrics"""
        if not market_data:
            return {}
        
        all_data = []
        daily_stats = {}
        
        # Combine all ticker data
        for ticker, data in market_data.items():
            data_copy = data.copy()
            data_copy['ticker'] = ticker
            
            # Calculate daily metrics for each ticker
            data_copy['daily_return'] = data_copy['close'].pct_change() * 100
            data_copy['volume_change'] = data_copy['volume'].pct_change() * 100
            data_copy['high_low_range'] = ((data_copy['high'] - data_copy['low']) / data_copy['close']) * 100
            data_copy['body_percent'] = abs((data_copy['close'] - data_copy['open']) / data_copy['close']) * 100
            data_copy['upper_shadow'] = ((data_copy['high'] - np.maximum(data_copy['open'], data_copy['close'])) / data_copy['close']) * 100
            data_copy['lower_shadow'] = ((np.minimum(data_copy['open'], data_copy['close']) - data_copy['low']) / data_copy['close']) * 100
            
            all_data.append(data_copy)
        
        # Combine all data
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # Calculate daily market-wide statistics
        for date in combined_df['date'].unique():
            day_data = combined_df[combined_df['date'] == date]
            
            if len(day_data) > 10:  # Minimum data requirement
                daily_stats[date] = {
                    'date': date,
                    'total_tickers': len(day_data),
                    
                    # Price Movement Metrics
                    'avg_daily_return': day_data['daily_return'].mean(),
                    'median_daily_return': day_data['daily_return'].median(),
                    'positive_return_pct': (day_data['daily_return'] > 0).sum() / len(day_data) * 100,
                    'strong_positive_pct': (day_data['daily_return'] > 2).sum() / len(day_data) * 100,
                    'strong_negative_pct': (day_data['daily_return'] < -2).sum() / len(day_data) * 100,
                    'return_std': day_data['daily_return'].std(),
                    
                    # Volume Metrics
                    'avg_volume_change': day_data['volume_change'].mean(),
                    'volume_expansion_pct': (day_data['volume_change'] > 20).sum() / len(day_data) * 100,
                    'volume_contraction_pct': (day_data['volume_change'] < -20).sum() / len(day_data) * 100,
                    
                    # Volatility Metrics
                    'avg_daily_range': day_data['high_low_range'].mean(),
                    'high_volatility_pct': (day_data['high_low_range'] > 4).sum() / len(day_data) * 100,
                    'low_volatility_pct': (day_data['high_low_range'] < 1.5).sum() / len(day_data) * 100,
                    
                    # Price Action Metrics
                    'avg_body_percent': day_data['body_percent'].mean(),
                    'strong_body_pct': (day_data['body_percent'] > 2).sum() / len(day_data) * 100,
                    'doji_pct': (day_data['body_percent'] < 0.5).sum() / len(day_data) * 100,
                    
                    # Shadow Analysis
                    'avg_upper_shadow': day_data['upper_shadow'].mean(),
                    'avg_lower_shadow': day_data['lower_shadow'].mean(),
                    'hammer_pct': ((day_data['lower_shadow'] > day_data['body_percent']) & 
                                 (day_data['upper_shadow'] < day_data['body_percent'])).sum() / len(day_data) * 100,
                    'shooting_star_pct': ((day_data['upper_shadow'] > day_data['body_percent']) & 
                                        (day_data['lower_shadow'] < day_data['body_percent'])).sum() / len(day_data) * 100,
                    
                    # Market Breadth
                    'advance_decline_ratio': (day_data['daily_return'] > 0).sum() / (day_data['daily_return'] < 0).sum() if (day_data['daily_return'] < 0).sum() > 0 else float('inf'),
                    
                    # Risk Metrics
                    'extreme_moves_pct': (abs(day_data['daily_return']) > 5).sum() / len(day_data) * 100,
                    'gap_up_pct': ((day_data['open'] - day_data['close'].shift(1)) / day_data['close'].shift(1) > 0.02).sum() / len(day_data) * 100,
                    'gap_down_pct': ((day_data['open'] - day_data['close'].shift(1)) / day_data['close'].shift(1) < -0.02).sum() / len(day_data) * 100,
                }
        
        return daily_stats
    
    def identify_market_regime(self, daily_stats):
        """Identify market regime characteristics"""
        if not daily_stats:
            return {}
        
        stats_df = pd.DataFrame(list(daily_stats.values()))
        
        regime_analysis = {
            'period_summary': {
                'start_date': stats_df['date'].min(),
                'end_date': stats_df['date'].max(),
                'total_days': len(stats_df),
                'avg_tickers_per_day': stats_df['total_tickers'].mean()
            },
            
            'market_direction': {
                'avg_daily_return': stats_df['avg_daily_return'].mean(),
                'positive_days_pct': (stats_df['avg_daily_return'] > 0).sum() / len(stats_df) * 100,
                'strong_up_days_pct': (stats_df['avg_daily_return'] > 1).sum() / len(stats_df) * 100,
                'strong_down_days_pct': (stats_df['avg_daily_return'] < -1).sum() / len(stats_df) * 100,
                'return_consistency': 1 / (1 + stats_df['return_std'].mean()),  # Higher = more consistent
            },
            
            'market_breadth': {
                'avg_positive_participation': stats_df['positive_return_pct'].mean(),
                'avg_strong_positive_participation': stats_df['strong_positive_pct'].mean(),
                'avg_advance_decline_ratio': stats_df['advance_decline_ratio'].replace([float('inf'), -float('inf')], np.nan).mean(),
                'breadth_consistency': stats_df['positive_return_pct'].std(),
            },
            
            'volatility_profile': {
                'avg_daily_range': stats_df['avg_daily_range'].mean(),
                'high_volatility_environment': stats_df['high_volatility_pct'].mean(),
                'low_volatility_environment': stats_df['low_volatility_pct'].mean(),
                'volatility_stability': 1 / (1 + stats_df['avg_daily_range'].std()),
            },
            
            'volume_characteristics': {
                'avg_volume_expansion': stats_df['volume_expansion_pct'].mean(),
                'avg_volume_contraction': stats_df['volume_contraction_pct'].mean(),
                'volume_activity_level': stats_df['avg_volume_change'].mean(),
            },
            
            'price_action_quality': {
                'strong_conviction_moves': stats_df['strong_body_pct'].mean(),
                'indecision_level': stats_df['doji_pct'].mean(),
                'reversal_signals': (stats_df['hammer_pct'] + stats_df['shooting_star_pct']).mean(),
            },
            
            'risk_environment': {
                'extreme_moves_frequency': stats_df['extreme_moves_pct'].mean(),
                'gap_activity': (stats_df['gap_up_pct'] + stats_df['gap_down_pct']).mean(),
                'market_stress_level': stats_df['extreme_moves_pct'].mean() + stats_df['return_std'].mean(),
            }
        }
        
        return regime_analysis
    
    def create_market_condition_signature(self, regime_analysis):
        """Create a unique signature for the market conditions"""
        if not regime_analysis:
            return {}
        
        signature = {
            'market_type': self._classify_market_type(regime_analysis),
            'volatility_regime': self._classify_volatility(regime_analysis),
            'breadth_regime': self._classify_breadth(regime_analysis),
            'volume_regime': self._classify_volume(regime_analysis),
            'risk_level': self._classify_risk(regime_analysis),
            'opportunity_score': self._calculate_opportunity_score(regime_analysis)
        }
        
        return signature
    
    def _classify_market_type(self, regime):
        """Classify the overall market type"""
        direction = regime['market_direction']
        avg_return = direction['avg_daily_return']
        positive_days = direction['positive_days_pct']
        
        if avg_return > 0.5 and positive_days > 60:
            return "Strong_Bull"
        elif avg_return > 0 and positive_days > 50:
            return "Mild_Bull"
        elif avg_return < -0.5 and positive_days < 40:
            return "Strong_Bear"
        elif avg_return < 0 and positive_days < 50:
            return "Mild_Bear"
        else:
            return "Sideways_Choppy"
    
    def _classify_volatility(self, regime):
        """Classify volatility regime"""
        vol = regime['volatility_profile']
        avg_range = vol['avg_daily_range']
        high_vol_pct = vol['high_volatility_environment']
        
        if avg_range > 4 or high_vol_pct > 30:
            return "High_Volatility"
        elif avg_range < 2 or vol['low_volatility_environment'] > 50:
            return "Low_Volatility"
        else:
            return "Normal_Volatility"
    
    def _classify_breadth(self, regime):
        """Classify market breadth"""
        breadth = regime['market_breadth']
        participation = breadth['avg_positive_participation']
        
        if participation > 65:
            return "Broad_Participation"
        elif participation < 35:
            return "Narrow_Participation"
        else:
            return "Selective_Participation"
    
    def _classify_volume(self, regime):
        """Classify volume regime"""
        volume = regime['volume_characteristics']
        expansion = volume['avg_volume_expansion']
        
        if expansion > 25:
            return "High_Volume_Activity"
        elif expansion < 10:
            return "Low_Volume_Activity"
        else:
            return "Normal_Volume_Activity"
    
    def _classify_risk(self, regime):
        """Classify risk environment"""
        risk = regime['risk_environment']
        stress_level = risk['market_stress_level']
        
        if stress_level > 8:
            return "High_Risk"
        elif stress_level < 4:
            return "Low_Risk"
        else:
            return "Moderate_Risk"
    
    def _calculate_opportunity_score(self, regime):
        """Calculate overall opportunity score (0-100)"""
        # Factors that contribute to good trading opportunities
        direction_score = min(abs(regime['market_direction']['avg_daily_return']) * 20, 25)
        volatility_score = min(regime['volatility_profile']['avg_daily_range'] * 5, 25)
        volume_score = min(regime['volume_characteristics']['avg_volume_expansion'] * 1, 25)
        breadth_score = min(abs(regime['market_breadth']['avg_positive_participation'] - 50) * 0.5, 25)
        
        total_score = direction_score + volatility_score + volume_score + breadth_score
        return min(max(total_score, 0), 100)
    
    def generate_condition_report(self, regime_analysis, signature):
        """Generate a comprehensive market condition report"""
        print("\n" + "="*80)
        print("MARKET CONDITION ANALYSIS - BROOKS STRATEGY SUCCESS PERIOD")
        print("="*80)
        
        period = regime_analysis['period_summary']
        print(f"Analysis Period: {period['start_date'].date()} to {period['end_date'].date()}")
        print(f"Total Trading Days: {period['total_days']}")
        print(f"Average Tickers Analyzed: {period['avg_tickers_per_day']:.0f}")
        print()
        
        # Market Signature
        print("MARKET CONDITION SIGNATURE:")
        print("-" * 40)
        for key, value in signature.items():
            print(f"{key.replace('_', ' ').title():<20}: {value}")
        print()
        
        # Detailed Metrics
        direction = regime_analysis['market_direction']
        print("MARKET DIRECTION METRICS:")
        print(f"  Average Daily Return: {direction['avg_daily_return']:.2f}%")
        print(f"  Positive Days: {direction['positive_days_pct']:.1f}%")
        print(f"  Strong Up Days (>1%): {direction['strong_up_days_pct']:.1f}%")
        print(f"  Strong Down Days (<-1%): {direction['strong_down_days_pct']:.1f}%")
        print()
        
        breadth = regime_analysis['market_breadth']
        print("MARKET BREADTH METRICS:")
        print(f"  Average Positive Participation: {breadth['avg_positive_participation']:.1f}%")
        print(f"  Strong Positive Participation: {breadth['avg_strong_positive_participation']:.1f}%")
        print(f"  Advance/Decline Ratio: {breadth['avg_advance_decline_ratio']:.2f}")
        print()
        
        vol = regime_analysis['volatility_profile']
        print("VOLATILITY METRICS:")
        print(f"  Average Daily Range: {vol['avg_daily_range']:.2f}%")
        print(f"  High Volatility Days: {vol['high_volatility_environment']:.1f}%")
        print(f"  Low Volatility Days: {vol['low_volatility_environment']:.1f}%")
        print()
        
        volume = regime_analysis['volume_characteristics']
        print("VOLUME METRICS:")
        print(f"  Volume Expansion Days: {volume['avg_volume_expansion']:.1f}%")
        print(f"  Volume Contraction Days: {volume['avg_volume_contraction']:.1f}%")
        print()
        
        risk = regime_analysis['risk_environment']
        print("RISK METRICS:")
        print(f"  Extreme Moves (>5%): {risk['extreme_moves_frequency']:.1f}%")
        print(f"  Gap Activity: {risk['gap_activity']:.1f}%")
        print(f"  Market Stress Level: {risk['market_stress_level']:.2f}")
        print()
        
        print("="*80)
        print("TRADING STRATEGY IMPLICATIONS:")
        print(f"• Opportunity Score: {signature['opportunity_score']:.0f}/100")
        print(f"• Market Type: {signature['market_type']}")
        print(f"• Best suited for: {self._get_strategy_recommendations(signature)}")
        print("="*80)
    
    def _get_strategy_recommendations(self, signature):
        """Get strategy recommendations based on market conditions"""
        recommendations = []
        
        if signature['market_type'] in ['Strong_Bull', 'Mild_Bull']:
            recommendations.append("Long-biased strategies")
        
        if signature['volatility_regime'] == 'High_Volatility':
            recommendations.append("Breakout strategies")
        
        if signature['breadth_regime'] == 'Broad_Participation':
            recommendations.append("Broad market strategies")
        
        if signature['volume_regime'] == 'High_Volume_Activity':
            recommendations.append("Momentum strategies")
        
        if signature['risk_level'] == 'Low_Risk':
            recommendations.append("Aggressive position sizing")
        
        return ", ".join(recommendations) if recommendations else "Cautious approach"
    
    def save_analysis_report(self, regime_analysis, signature, output_file=None):
        """Save detailed analysis to Excel"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(self.script_dir, f"market_condition_analysis_{timestamp}.xlsx")
        
        try:
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Market signature
                signature_df = pd.DataFrame([signature])
                signature_df.to_excel(writer, sheet_name='Market_Signature', index=False)
                
                # Regime analysis
                regime_df = pd.DataFrame([regime_analysis['period_summary']])
                for category, metrics in regime_analysis.items():
                    if category != 'period_summary' and isinstance(metrics, dict):
                        temp_df = pd.DataFrame([metrics])
                        temp_df.columns = [f"{category}_{col}" for col in temp_df.columns]
                        regime_df = pd.concat([regime_df, temp_df], axis=1)
                
                regime_df.to_excel(writer, sheet_name='Regime_Analysis', index=False)
            
            logger.info(f"Analysis report saved to: {output_file}")
            return output_file
        
        except Exception as e:
            logger.error(f"Error saving analysis report: {e}")
            return None

def main():
    """Main function to analyze market conditions during Brooks strategy success"""
    try:
        analyzer = MarketConditionAnalyzer()
        
        # Define the period when Brooks strategy performed well (May 20-24, 2025)
        start_date = datetime(2025, 5, 20)
        end_date = datetime(2025, 5, 24)
        
        logger.info(f"Analyzing market conditions from {start_date.date()} to {end_date.date()}")
        
        # Load ticker universe
        tickers = analyzer.load_ticker_universe()
        if not tickers:
            logger.error("Could not load ticker universe")
            return
        
        # Load market data
        market_data = analyzer.load_ohlc_data_for_period(tickers, start_date, end_date)
        if not market_data:
            logger.error("Could not load market data")
            return
        
        # Calculate market metrics
        daily_stats = analyzer.calculate_market_metrics(market_data)
        
        # Analyze market regime
        regime_analysis = analyzer.identify_market_regime(daily_stats)
        
        # Create market signature
        signature = analyzer.create_market_condition_signature(regime_analysis)
        
        # Generate report
        analyzer.generate_condition_report(regime_analysis, signature)
        
        # Save detailed analysis
        report_file = analyzer.save_analysis_report(regime_analysis, signature)
        if report_file:
            print(f"\nDetailed analysis saved to: {report_file}")
        
        logger.info("Market condition analysis completed successfully")
        
    except Exception as e:
        logger.error(f"Error in market condition analysis: {e}")
        raise

if __name__ == "__main__":
    main()