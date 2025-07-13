#!/usr/bin/env python3
"""
Analyze Long Reversal Daily files for volume exhaustion patterns after momentum peaks.
Track tickers across multiple days to identify Entry → Build → Peak → Exit cycles.
Enhanced version that pulls historical data from Zerodha for comprehensive analysis.
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from collections import defaultdict
import glob
import json
from kiteconnect import KiteConnect
import logging
import configparser
import matplotlib.pyplot as plt
import seaborn as sns

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VolumeExhaustionAnalyzer:
    def __init__(self):
        self.config = self.load_config()
        self.kite = None
        self.ticker_history = defaultdict(list)
        self.volume_patterns = []
        
    def load_config(self):
        """Load configuration from Daily/config.ini file"""
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
        
        if not os.path.exists(config_path):
            logger.error(f"config.ini file not found at {config_path}")
            raise FileNotFoundError(f"config.ini file not found at {config_path}")
        
        config = configparser.ConfigParser()
        config.read(config_path)
        
        return config
        
    def setup_kite_connection(self):
        """Setup Zerodha KiteConnect API connection"""
        try:
            # Use Sai's credentials which have access token
            api_key = self.config.get('API_CREDENTIALS_Sai', 'api_key')
            api_secret = self.config.get('API_CREDENTIALS_Sai', 'api_secret')
            access_token = self.config.get('API_CREDENTIALS_Sai', 'access_token')
            
            self.kite = KiteConnect(api_key=api_key)
            self.kite.set_access_token(access_token)
            
            # Test connection
            profile = self.kite.profile()
            logger.info(f"Connected to Zerodha API. User: {profile['user_name']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup Kite connection: {str(e)}")
            return False
    
    def get_historical_data(self, ticker, from_date, to_date):
        """Get historical data from Zerodha API"""
        try:
            # Get instrument token
            try:
                instruments = self.kite.ltp([f"NSE:{ticker}"])
                if not instruments or f"NSE:{ticker}" not in instruments:
                    logger.warning(f"Could not find instrument token for {ticker}")
                    return None
                
                instrument_token = list(instruments.values())[0]['instrument_token']
            except Exception as e:
                logger.warning(f"Could not get instrument token for {ticker}: {str(e)}")
                return None
            
            # Fetch historical data
            try:
                historical_data = self.kite.historical_data(
                    instrument_token=instrument_token,
                    from_date=from_date,
                    to_date=to_date,
                    interval="day"
                )
                
                if historical_data:
                    df = pd.DataFrame(historical_data)
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
                    return df
            except Exception as e:
                logger.warning(f"Could not fetch historical data for {ticker}: {str(e)}")
                return None
            
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {str(e)}")
            
        return None
    
    def load_scanner_results(self):
        """Load all Long Reversal Daily scanner results"""
        results_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/results"
        pattern = os.path.join(results_dir, "Long_Reversal_Daily_*.xlsx")
        files = sorted(glob.glob(pattern))
        
        logger.info(f"Found {len(files)} Long Reversal Daily files")
        
        # Process each file
        for file_path in files:
            filename = os.path.basename(file_path)
            date_str = filename.replace("Long_Reversal_Daily_", "").replace(".xlsx", "")
            
            try:
                # Parse date
                file_date = datetime.strptime(date_str[:8], "%Y%m%d")
                file_time = date_str[9:15]
                
                # Fix year if it's 2025 (likely a typo, should be 2024)
                if file_date.year == 2025:
                    file_date = file_date.replace(year=2024)
                
                # Read Excel file
                df = pd.read_excel(file_path)
                
                # Store data for each ticker
                for _, row in df.iterrows():
                    ticker = row.get('Ticker', row.get('ticker', row.get('TICKER', None)))
                    if ticker:
                        ticker_data = {
                            'date': file_date,
                            'time': file_time,
                            'filename': filename,
                            'data': row.to_dict()
                        }
                        self.ticker_history[ticker].append(ticker_data)
                        
            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
        
        logger.info(f"Loaded data for {len(self.ticker_history)} unique tickers")
    
    def analyze_volume_exhaustion(self, ticker, appearances):
        """Analyze a ticker for volume exhaustion patterns"""
        if len(appearances) < 3:
            return None
            
        # Sort by date
        appearances.sort(key=lambda x: (x['date'], x['time']))
        
        # Get date range for historical data
        first_date = appearances[0]['date']
        last_date = appearances[-1]['date']
        
        # Fetch historical data with buffer
        from_date = first_date - timedelta(days=30)  # 30 days before first appearance
        to_date = min(last_date + timedelta(days=30), datetime.now())  # 30 days after or today
        
        hist_data = self.get_historical_data(ticker, from_date, to_date)
        
        if hist_data is None or len(hist_data) < 50:
            return None
        
        # Calculate technical indicators
        hist_data['SMA_20'] = hist_data['close'].rolling(window=20).mean()
        hist_data['SMA_50'] = hist_data['close'].rolling(window=50).mean()
        hist_data['Volume_SMA_20'] = hist_data['volume'].rolling(window=20).mean()
        hist_data['RSI'] = self.calculate_rsi(hist_data['close'])
        
        # Analyze each appearance
        pattern_data = {
            'ticker': ticker,
            'appearances': len(appearances),
            'first_date': first_date,
            'last_date': last_date,
            'score_progression': [],
            'volume_pattern': [],
            'price_pattern': [],
            'momentum_pattern': []
        }
        
        for i, appearance in enumerate(appearances):
            data = appearance['data']
            signal_date = appearance['date']
            
            # Get score
            score = data.get('Score', data.get('score', data.get('SCORE', 
                            data.get('Total_Score', data.get('total_score', 0)))))
            # Convert to float if it's a string
            try:
                score = float(score)
            except (ValueError, TypeError):
                score = 0.0
            pattern_data['score_progression'].append(score)
            
            # Get market data around signal date
            if signal_date in hist_data.index:
                idx = hist_data.index.get_loc(signal_date)
                
                # Get 5-day window around signal
                start_idx = max(0, idx - 2)
                end_idx = min(len(hist_data), idx + 3)
                
                window_data = hist_data.iloc[start_idx:end_idx]
                
                # Volume analysis
                avg_volume = window_data['volume'].mean()
                volume_ratio = avg_volume / hist_data['Volume_SMA_20'].iloc[idx] if hist_data['Volume_SMA_20'].iloc[idx] > 0 else 1
                pattern_data['volume_pattern'].append(volume_ratio)
                
                # Price momentum
                price_change = (hist_data['close'].iloc[idx] - hist_data['close'].iloc[max(0, idx-5)]) / hist_data['close'].iloc[max(0, idx-5)] * 100
                pattern_data['price_pattern'].append(price_change)
                
                # RSI momentum
                if not pd.isna(hist_data['RSI'].iloc[idx]):
                    pattern_data['momentum_pattern'].append(hist_data['RSI'].iloc[idx])
        
        # Identify exhaustion patterns
        exhaustion_signals = self.identify_exhaustion_signals(pattern_data, hist_data)
        pattern_data['exhaustion_signals'] = exhaustion_signals
        
        return pattern_data
    
    def calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def identify_exhaustion_signals(self, pattern_data, hist_data):
        """Identify specific exhaustion signals"""
        signals = []
        
        scores = pattern_data['score_progression']
        volumes = pattern_data['volume_pattern']
        momentum = pattern_data['momentum_pattern']
        
        if len(scores) >= 3:
            # 1. Score Peak Pattern
            max_score = max(scores)
            max_score_idx = scores.index(max_score)
            
            if max_score_idx > 0 and max_score_idx < len(scores) - 1:
                # Check for declining scores after peak
                post_peak_decline = all(scores[i] <= scores[i-1] for i in range(max_score_idx + 1, len(scores)))
                
                if post_peak_decline:
                    signals.append({
                        'type': 'Score Peak Exhaustion',
                        'peak_index': max_score_idx,
                        'peak_score': max_score,
                        'decline_rate': (max_score - scores[-1]) / max_score * 100
                    })
            
            # 2. Volume Exhaustion Pattern
            if volumes:
                # Look for declining volume on rallies
                if len(volumes) >= 3:
                    recent_volumes = volumes[-3:]
                    if all(v < 1.0 for v in recent_volumes[-2:]) and max(volumes) > 1.5:
                        signals.append({
                            'type': 'Volume Exhaustion',
                            'peak_volume_ratio': max(volumes),
                            'current_volume_ratio': volumes[-1]
                        })
            
            # 3. Momentum Divergence
            if momentum and len(momentum) >= 3:
                # Check for bearish divergence (price up, RSI down)
                if momentum[-1] < momentum[-2] and scores[-1] >= scores[-2]:
                    signals.append({
                        'type': 'Bearish Divergence',
                        'rsi_decline': momentum[-2] - momentum[-1]
                    })
                
                # Overbought exhaustion
                if any(rsi > 70 for rsi in momentum) and momentum[-1] < 70:
                    signals.append({
                        'type': 'Overbought Exhaustion',
                        'peak_rsi': max(momentum),
                        'current_rsi': momentum[-1]
                    })
        
        return signals
    
    def generate_report(self):
        """Generate comprehensive report on volume exhaustion patterns"""
        exhaustion_candidates = []
        all_patterns = []
        
        # Analyze each ticker with multiple appearances
        multi_appearance_tickers = {ticker: history for ticker, history in self.ticker_history.items() 
                                   if len(history) >= 3}
        
        logger.info(f"Analyzing {len(multi_appearance_tickers)} tickers with 3+ appearances")
        
        analysis_count = 0
        for ticker, history in multi_appearance_tickers.items():
            pattern_data = self.analyze_volume_exhaustion(ticker, history)
            
            if pattern_data:
                all_patterns.append(pattern_data)
                if pattern_data['exhaustion_signals']:
                    exhaustion_candidates.append(pattern_data)
                
                analysis_count += 1
                if analysis_count % 50 == 0:
                    logger.info(f"Analyzed {analysis_count} tickers...")
        
        # Sort by number of exhaustion signals
        exhaustion_candidates.sort(key=lambda x: len(x['exhaustion_signals']), reverse=True)
        
        # Generate report
        print("\n" + "="*80)
        print("VOLUME EXHAUSTION PATTERN ANALYSIS - LONG REVERSAL SIGNALS")
        print("="*80)
        print(f"\nAnalysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Tickers Analyzed: {len(multi_appearance_tickers)}")
        print(f"Successfully Analyzed: {len(all_patterns)}")
        print(f"Exhaustion Candidates Found: {len(exhaustion_candidates)}")
        
        # Show some patterns even if no exhaustion signals
        if not exhaustion_candidates and all_patterns:
            print("\n" + "-"*80)
            print("TICKER PATTERNS (Score Progression Analysis)")
            print("-"*80)
            
            # Sort by number of appearances and score decline
            patterns_with_decline = []
            for pattern in all_patterns:
                if pattern['score_progression'] and len(pattern['score_progression']) >= 3:
                    max_score = max(pattern['score_progression'])
                    latest_score = pattern['score_progression'][-1]
                    decline = max_score - latest_score
                    if decline > 10:  # At least 10 point decline
                        pattern['score_decline'] = decline
                        patterns_with_decline.append(pattern)
            
            patterns_with_decline.sort(key=lambda x: x['score_decline'], reverse=True)
            
            for i, pattern in enumerate(patterns_with_decline[:20], 1):
                print(f"\n{i}. {pattern['ticker']}")
                print(f"   Appearances: {pattern['appearances']}")
                print(f"   Date Range: {pattern['first_date'].strftime('%Y-%m-%d')} to {pattern['last_date'].strftime('%Y-%m-%d')}")
                print(f"   Score Progression: {' → '.join([f'{s:.1f}' for s in pattern['score_progression']])}")
                print(f"   Score Decline: {pattern['score_decline']:.1f} points")
                
                if pattern['volume_pattern']:
                    print(f"   Volume Pattern: {' → '.join([f'{v:.2f}x' for v in pattern['volume_pattern']])}")
        
        if exhaustion_candidates:
            print("\n" + "-"*80)
            print("TOP EXHAUSTION CANDIDATES (Entry → Build → Peak → Exit)")
            print("-"*80)
            
            for i, candidate in enumerate(exhaustion_candidates[:20], 1):
                print(f"\n{i}. {candidate['ticker']}")
                print(f"   Appearances: {candidate['appearances']}")
                print(f"   Date Range: {candidate['first_date'].strftime('%Y-%m-%d')} to {candidate['last_date'].strftime('%Y-%m-%d')}")
                print(f"   Score Progression: {' → '.join([f'{s:.1f}' for s in candidate['score_progression']])}")
                
                if candidate['volume_pattern']:
                    print(f"   Volume Pattern: {' → '.join([f'{v:.2f}x' for v in candidate['volume_pattern']])}")
                
                print(f"   Exhaustion Signals:")
                for signal in candidate['exhaustion_signals']:
                    print(f"      - {signal['type']}")
                    if signal['type'] == 'Score Peak Exhaustion':
                        print(f"        Peak Score: {signal['peak_score']:.1f}, Decline: {signal['decline_rate']:.1f}%")
                    elif signal['type'] == 'Volume Exhaustion':
                        print(f"        Peak Volume: {signal['peak_volume_ratio']:.2f}x, Current: {signal['current_volume_ratio']:.2f}x")
                    elif signal['type'] == 'Bearish Divergence':
                        print(f"        RSI Decline: {signal['rsi_decline']:.1f}")
                    elif signal['type'] == 'Overbought Exhaustion':
                        print(f"        Peak RSI: {signal['peak_rsi']:.1f}, Current: {signal['current_rsi']:.1f}")
        
        # Save detailed results
        self.save_results(exhaustion_candidates)
        
        return exhaustion_candidates
    
    def save_results(self, exhaustion_candidates):
        """Save analysis results"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Prepare data for Excel
        excel_data = []
        for candidate in exhaustion_candidates:
            row = {
                'Ticker': candidate['ticker'],
                'Appearances': candidate['appearances'],
                'First_Date': candidate['first_date'],
                'Last_Date': candidate['last_date'],
                'Score_Progression': ', '.join([f'{s:.1f}' for s in candidate['score_progression']]),
                'Exhaustion_Signal_Count': len(candidate['exhaustion_signals']),
                'Exhaustion_Types': ', '.join([s['type'] for s in candidate['exhaustion_signals']])
            }
            
            # Add latest scores
            if candidate['score_progression']:
                row['Latest_Score'] = candidate['score_progression'][-1]
                row['Peak_Score'] = max(candidate['score_progression'])
                row['Score_Decline'] = row['Peak_Score'] - row['Latest_Score']
            
            excel_data.append(row)
        
        # Save to Excel
        if excel_data:
            df = pd.DataFrame(excel_data)
            output_file = f'/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/volume_exhaustion_analysis_{timestamp}.xlsx'
            df.to_excel(output_file, index=False)
            logger.info(f"Results saved to {output_file}")
        
        # Save detailed JSON
        json_file = f'/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/volume_exhaustion_detailed_{timestamp}.json'
        with open(json_file, 'w') as f:
            json.dump(exhaustion_candidates, f, indent=4, default=str)
        logger.info(f"Detailed results saved to {json_file}")
    
    def create_visualizations(self, exhaustion_candidates):
        """Create visualization plots"""
        if not exhaustion_candidates:
            return
            
        plt.style.use('seaborn-v0_8-darkgrid')
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # 1. Score progression patterns
        ax1 = axes[0, 0]
        for candidate in exhaustion_candidates[:5]:  # Top 5
            scores = candidate['score_progression']
            x = range(len(scores))
            ax1.plot(x, scores, marker='o', label=candidate['ticker'])
        
        ax1.set_title('Score Progression - Top Exhaustion Candidates')
        ax1.set_xlabel('Appearance Number')
        ax1.set_ylabel('Score')
        ax1.legend()
        
        # 2. Volume patterns
        ax2 = axes[0, 1]
        volume_data = []
        labels = []
        
        for candidate in exhaustion_candidates[:10]:
            if candidate['volume_pattern']:
                volume_data.append(candidate['volume_pattern'])
                labels.append(candidate['ticker'])
        
        if volume_data:
            positions = range(len(volume_data))
            for i, (volumes, label) in enumerate(zip(volume_data, labels)):
                x = [i + j*0.1 for j in range(len(volumes))]
                ax2.scatter(x, volumes, label=label)
            
            ax2.set_title('Volume Patterns (Volume/20-SMA)')
            ax2.set_xlabel('Ticker')
            ax2.set_ylabel('Volume Ratio')
            ax2.axhline(y=1.0, color='r', linestyle='--', alpha=0.5)
        
        # 3. Exhaustion signal distribution
        ax3 = axes[1, 0]
        signal_types = defaultdict(int)
        for candidate in exhaustion_candidates:
            for signal in candidate['exhaustion_signals']:
                signal_types[signal['type']] += 1
        
        if signal_types:
            ax3.bar(signal_types.keys(), signal_types.values())
            ax3.set_title('Distribution of Exhaustion Signal Types')
            ax3.set_xlabel('Signal Type')
            ax3.set_ylabel('Count')
            plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # 4. Days between appearances
        ax4 = axes[1, 1]
        days_between = []
        for candidate in exhaustion_candidates[:20]:
            if candidate['appearances'] >= 2:
                first = candidate['first_date']
                last = candidate['last_date']
                days = (last - first).days
                days_between.append(days)
        
        if days_between:
            ax4.hist(days_between, bins=20, edgecolor='black')
            ax4.set_title('Days Between First and Last Appearance')
            ax4.set_xlabel('Days')
            ax4.set_ylabel('Count')
        
        plt.tight_layout()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        plt.savefig(f'/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/volume_exhaustion_charts_{timestamp}.png', dpi=300)
        plt.close()
        logger.info("Visualizations saved")
    
    def run_analysis(self):
        """Run the complete volume exhaustion analysis"""
        # Setup Kite connection
        if not self.setup_kite_connection():
            logger.error("Failed to setup Kite connection")
            return False
        
        # Load scanner results
        self.load_scanner_results()
        
        # Generate report
        exhaustion_candidates = self.generate_report()
        
        # Create visualizations
        self.create_visualizations(exhaustion_candidates)
        
        # Trading recommendations
        print("\n" + "="*80)
        print("TRADING RECOMMENDATIONS")
        print("="*80)
        
        print("\n1. EXIT SIGNALS:")
        print("   - Tickers showing multiple exhaustion signals should be considered for exit")
        print("   - Score Peak Exhaustion + Volume Exhaustion = Strong exit signal")
        print("   - Bearish Divergence confirms weakness")
        
        print("\n2. AVOID NEW ENTRIES:")
        print("   - Do not enter positions in tickers showing exhaustion patterns")
        print("   - Wait for consolidation and new accumulation phase")
        
        print("\n3. RISK MANAGEMENT:")
        print("   - Tighten stops on positions showing early exhaustion signs")
        print("   - Consider partial profit booking on overbought exhaustion")
        
        print("\n4. WATCH LIST:")
        print("   - Monitor exhausted tickers for potential re-entry after base building")
        print("   - Look for volume expansion on future breakouts")
        
        return True


def main():
    analyzer = VolumeExhaustionAnalyzer()
    analyzer.run_analysis()


if __name__ == "__main__":
    main()