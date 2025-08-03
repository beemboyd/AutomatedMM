#!/usr/bin/env python3
"""
Stop Loss Analysis for Brooks Higher Probability LONG Reversal Strategy
Analyze optimal stop loss mechanisms based on actual trade data
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StopLossAnalyzer:
    def __init__(self):
        self.results_path = "/Users/maverick/PycharmProjects/India-TS/Daily/results"
        self.data_path = "/Users/maverick/PycharmProjects/India-TS/ML/data/ohlc_data/daily"
        self.pattern = "Brooks_Higher_Probability_LONG_Reversal_*.xlsx"
        
    def load_all_brooks_data(self):
        """Load all Brooks reversal files and combine data"""
        files = glob.glob(os.path.join(self.results_path, self.pattern))
        files.sort()
        
        all_data = []
        
        for file_path in files:
            try:
                df = pd.read_excel(file_path)
                # Extract date from filename
                filename = os.path.basename(file_path)
                date_parts = filename.split('_')[-3:-1]  # Get date and time parts
                file_date = '_'.join(date_parts)
                df['file_date'] = file_date
                df['file_path'] = file_path
                all_data.append(df)
                logger.info(f"Loaded {len(df)} records from {filename}")
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
                
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            logger.info(f"Total records loaded: {len(combined_df)}")
            return combined_df
        return pd.DataFrame()
    
    def get_price_history(self, ticker, entry_date, days_forward=10):
        """Get price history for a ticker after entry date"""
        try:
            file_path = os.path.join(self.data_path, f"{ticker}_day.csv")
            if not os.path.exists(file_path):
                return None
                
            df = pd.read_csv(file_path)
            df['date'] = pd.to_datetime(df['date'])
            
            # Convert entry_date string to datetime
            if isinstance(entry_date, str):
                # Parse various date formats from filename
                if '_' in entry_date:
                    date_str = entry_date.replace('_', ' ')
                    try:
                        entry_dt = datetime.strptime(date_str, "%d %m %Y %H")
                    except:
                        # Try different format
                        entry_dt = datetime.strptime(date_str.split()[0], "%d")
                        # Assume current month/year for now
                        entry_dt = datetime(2025, 5, int(date_str.split()[0]))
                else:
                    entry_dt = datetime.strptime(entry_date, "%Y-%m-%d")
            else:
                entry_dt = entry_date
            
            # Find data from entry date onwards
            future_data = df[df['date'] >= entry_dt].head(days_forward)
            return future_data[['date', 'open', 'high', 'low', 'close']].copy()
            
        except Exception as e:
            logger.warning(f"Error getting price history for {ticker}: {e}")
            return None
    
    def analyze_existing_stop_losses(self, brooks_data):
        """Analyze the stop loss levels in the Brooks files"""
        print("\n" + "="*60)
        print("1. EXISTING STOP LOSS ANALYSIS")
        print("="*60)
        
        # Analyze stop loss distribution
        brooks_data['stop_loss_pct'] = ((brooks_data['Entry_Price'] - brooks_data['Stop_Loss']) / brooks_data['Entry_Price']) * 100
        brooks_data['risk_pct'] = (brooks_data['Risk'] / brooks_data['Entry_Price']) * 100
        
        print("Stop Loss Statistics:")
        print(f"Average Stop Loss %: {brooks_data['stop_loss_pct'].mean():.2f}%")
        print(f"Median Stop Loss %: {brooks_data['stop_loss_pct'].median():.2f}%")
        print(f"Stop Loss Range: {brooks_data['stop_loss_pct'].min():.2f}% to {brooks_data['stop_loss_pct'].max():.2f}%")
        print(f"Standard Deviation: {brooks_data['stop_loss_pct'].std():.2f}%")
        
        # Risk analysis
        print(f"\nRisk Statistics:")
        print(f"Average Risk Amount: ₹{brooks_data['Risk'].mean():.2f}")
        print(f"Average Risk %: {brooks_data['risk_pct'].mean():.2f}%")
        
        # ATR relationship
        brooks_data['atr_multiple'] = brooks_data['stop_loss_pct'] / (brooks_data['ATR'] / brooks_data['Entry_Price'] * 100)
        print(f"\nATR Relationship:")
        print(f"Average ATR Multiple: {brooks_data['atr_multiple'].mean():.2f}x")
        print(f"ATR Multiple Range: {brooks_data['atr_multiple'].min():.2f}x to {brooks_data['atr_multiple'].max():.2f}x")
        
        return brooks_data
    
    def analyze_price_movements(self, brooks_data):
        """Study price movements post-entry to determine hit rates"""
        print("\n" + "="*60)
        print("2. PRICE MOVEMENT ANALYSIS")
        print("="*60)
        
        # Sample analysis on subset due to data complexity
        sample_tickers = ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 'KOTAKBANK', 'LT', 'WIPRO']
        available_tickers = brooks_data[brooks_data['Ticker'].isin(sample_tickers)]['Ticker'].unique()
        
        stop_hit_analysis = []
        
        for ticker in available_tickers[:5]:  # Analyze first 5 available tickers
            ticker_trades = brooks_data[brooks_data['Ticker'] == ticker]
            
            for _, trade in ticker_trades.iterrows():
                price_history = self.get_price_history(ticker, trade['file_date'], days_forward=10)
                
                if price_history is not None and len(price_history) > 1:
                    entry_price = trade['Entry_Price']
                    stop_loss = trade['Stop_Loss']
                    
                    # Check if stop was hit in next 10 days
                    min_price = price_history['low'].min()
                    stop_hit = min_price <= stop_loss
                    
                    # Calculate maximum adverse excursion (MAE)
                    mae = ((entry_price - min_price) / entry_price) * 100
                    
                    # Calculate maximum favorable excursion (MFE)
                    max_price = price_history['high'].max()
                    mfe = ((max_price - entry_price) / entry_price) * 100
                    
                    stop_hit_analysis.append({
                        'ticker': ticker,
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'stop_loss_pct': trade['stop_loss_pct'],
                        'atr': trade['ATR'],
                        'stop_hit': stop_hit,
                        'mae': mae,
                        'mfe': mfe,
                        'risk_reward': trade['Risk_Reward_Ratio']
                    })
        
        if stop_hit_analysis:
            analysis_df = pd.DataFrame(stop_hit_analysis)
            
            print(f"Sample Analysis Results ({len(analysis_df)} trades):")
            print(f"Stop Hit Rate: {analysis_df['stop_hit'].mean():.1%}")
            print(f"Average MAE: {analysis_df['mae'].mean():.2f}%")
            print(f"Average MFE: {analysis_df['mfe'].mean():.2f}%")
            
            # Analyze by stop loss percentage ranges
            analysis_df['stop_range'] = pd.cut(analysis_df['stop_loss_pct'], 
                                             bins=[0, 2, 3, 4, 5, 10], 
                                             labels=['0-2%', '2-3%', '3-4%', '4-5%', '5%+'])
            
            stop_range_analysis = analysis_df.groupby('stop_range').agg({
                'stop_hit': 'mean',
                'mae': 'mean',
                'mfe': 'mean'
            }).round(3)
            
            print("\nStop Hit Rate by Stop Loss Range:")
            print(stop_range_analysis.to_string())
            
            return analysis_df
        
        return None
    
    def compare_stop_loss_methods(self, brooks_data):
        """Compare different stop loss methods"""
        print("\n" + "="*60)
        print("3. STOP LOSS METHOD COMPARISON")
        print("="*60)
        
        # Calculate various stop loss methods
        methods_comparison = brooks_data.copy()
        
        # Method 1: Current method (existing)
        methods_comparison['current_stop_pct'] = methods_comparison['stop_loss_pct']
        
        # Method 2: Fixed percentage stops
        methods_comparison['fixed_2pct_stop'] = 2.0
        methods_comparison['fixed_3pct_stop'] = 3.0
        methods_comparison['fixed_4pct_stop'] = 4.0
        
        # Method 3: ATR-based stops
        methods_comparison['atr_pct'] = (methods_comparison['ATR'] / methods_comparison['Entry_Price']) * 100
        methods_comparison['atr_1x_stop'] = methods_comparison['atr_pct'] * 1.0
        methods_comparison['atr_1_5x_stop'] = methods_comparison['atr_pct'] * 1.5
        methods_comparison['atr_2x_stop'] = methods_comparison['atr_pct'] * 2.0
        
        # Method 4: Risk-adjusted stops
        target_risk_pct = 2.0  # Target 2% risk
        methods_comparison['risk_adjusted_stop'] = target_risk_pct
        
        print("Stop Loss Method Comparison:")
        print(f"Current Method - Avg: {methods_comparison['current_stop_pct'].mean():.2f}%, Std: {methods_comparison['current_stop_pct'].std():.2f}%")
        print(f"Fixed 2% Stop - All trades at 2.00%")
        print(f"Fixed 3% Stop - All trades at 3.00%")
        print(f"Fixed 4% Stop - All trades at 4.00%")
        print(f"ATR 1.0x Stop - Avg: {methods_comparison['atr_1x_stop'].mean():.2f}%, Std: {methods_comparison['atr_1x_stop'].std():.2f}%")
        print(f"ATR 1.5x Stop - Avg: {methods_comparison['atr_1_5x_stop'].mean():.2f}%, Std: {methods_comparison['atr_1_5x_stop'].std():.2f}%")
        print(f"ATR 2.0x Stop - Avg: {methods_comparison['atr_2x_stop'].mean():.2f}%, Std: {methods_comparison['atr_2x_stop'].std():.2f}%")
        
        # Risk-reward implications
        print(f"\nRisk-Reward Analysis:")
        avg_target1_pct = ((methods_comparison['Target1'] - methods_comparison['Entry_Price']) / methods_comparison['Entry_Price'] * 100).mean()
        
        print(f"Average Target 1: {avg_target1_pct:.2f}%")
        
        for method in ['fixed_2pct_stop', 'fixed_3pct_stop', 'atr_1_5x_stop']:
            if method == 'fixed_2pct_stop':
                stop_pct = 2.0
                method_name = "Fixed 2%"
            elif method == 'fixed_3pct_stop':
                stop_pct = 3.0
                method_name = "Fixed 3%"
            else:
                stop_pct = methods_comparison['atr_1_5x_stop'].mean()
                method_name = "ATR 1.5x"
            
            risk_reward = avg_target1_pct / stop_pct if stop_pct > 0 else 0
            print(f"{method_name} - Risk:Reward = 1:{risk_reward:.2f}")
        
        return methods_comparison
    
    def analyze_dynamic_stops(self, brooks_data):
        """Analyze potential for trailing stops"""
        print("\n" + "="*60)
        print("4. DYNAMIC/TRAILING STOP ANALYSIS")
        print("="*60)
        
        # For this analysis, we'll simulate different trailing stop approaches
        print("Trailing Stop Concepts:")
        print("1. ATR-based trailing: Trail by 1.5x ATR from highest point")
        print("2. Percentage trailing: Trail by 3% from highest point")
        print("3. Support-based trailing: Trail based on recent swing lows")
        
        # Simulate trailing stop performance on sample data
        sample_data = brooks_data.sample(min(50, len(brooks_data)))
        
        trailing_analysis = []
        
        for _, trade in sample_data.iterrows():
            entry_price = trade['Entry_Price']
            atr = trade['ATR']
            
            # Simulate price movement (basic simulation)
            # In real implementation, would use actual price data
            days = 10
            price_path = [entry_price]
            
            # Simple random walk simulation for demonstration
            np.random.seed(42)  # For reproducible results
            for day in range(days):
                change = np.random.normal(0.002, 0.02)  # 0.2% avg daily return, 2% volatility
                new_price = price_path[-1] * (1 + change)
                price_path.append(new_price)
            
            # Calculate trailing stops
            atr_trail_stops = []
            pct_trail_stops = []
            highest_price = entry_price
            
            for price in price_path[1:]:
                if price > highest_price:
                    highest_price = price
                
                # ATR trailing stop
                atr_trail_stop = highest_price - (1.5 * atr)
                atr_trail_stops.append(atr_trail_stop)
                
                # Percentage trailing stop
                pct_trail_stop = highest_price * 0.97  # 3% trailing
                pct_trail_stops.append(pct_trail_stop)
            
            # Calculate which method would be better
            final_price = price_path[-1]
            fixed_stop = entry_price - (entry_price * 0.03)  # 3% fixed stop
            
            # Determine outcomes
            fixed_stop_hit = min(price_path) <= fixed_stop
            atr_trail_hit = any(price_path[i+1] <= atr_trail_stops[i] for i in range(len(atr_trail_stops)))
            pct_trail_hit = any(price_path[i+1] <= pct_trail_stops[i] for i in range(len(pct_trail_stops)))
            
            trailing_analysis.append({
                'ticker': trade['Ticker'],
                'fixed_stop_hit': fixed_stop_hit,
                'atr_trail_hit': atr_trail_hit,
                'pct_trail_hit': pct_trail_hit,
                'final_return': (final_price - entry_price) / entry_price * 100
            })
        
        if trailing_analysis:
            trail_df = pd.DataFrame(trailing_analysis)
            print(f"\nTrailing Stop Simulation Results (N={len(trail_df)}):")
            print(f"Fixed Stop Hit Rate: {trail_df['fixed_stop_hit'].mean():.1%}")
            print(f"ATR Trailing Hit Rate: {trail_df['atr_trail_hit'].mean():.1%}")
            print(f"Percentage Trailing Hit Rate: {trail_df['pct_trail_hit'].mean():.1%}")
        
        return trailing_analysis
    
    def generate_stop_loss_recommendations(self, brooks_data, methods_comparison):
        """Generate comprehensive stop loss recommendations"""
        print("\n" + "="*60)
        print("5. STOP LOSS RECOMMENDATIONS")
        print("="*60)
        
        current_avg_stop = brooks_data['stop_loss_pct'].mean()
        atr_avg = (brooks_data['ATR'] / brooks_data['Entry_Price'] * 100).mean()
        
        recommendations = {
            'primary_method': None,
            'backup_method': None,
            'dynamic_adjustments': [],
            'risk_management': []
        }
        
        print("RECOMMENDED STOP LOSS FRAMEWORK:")
        print("-" * 40)
        
        # Primary recommendation
        if atr_avg > 0:
            recommended_atr_multiple = 1.5
            print(f"PRIMARY METHOD: ATR-Based Stop Loss")
            print(f"- Use {recommended_atr_multiple}x ATR as stop distance")
            print(f"- Current avg ATR: {atr_avg:.2f}%")
            print(f"- Recommended avg stop: {atr_avg * recommended_atr_multiple:.2f}%")
            print(f"- Provides volatility-adjusted stops")
            
            recommendations['primary_method'] = f"ATR {recommended_atr_multiple}x"
        
        # Backup method
        print(f"\nBACKUP METHOD: Fixed Percentage Stop")
        print(f"- Use 3% fixed stop when ATR unavailable")
        print(f"- Provides consistency and simplicity")
        
        recommendations['backup_method'] = "Fixed 3%"
        
        # Dynamic adjustments
        print(f"\nDYNAMIC ADJUSTMENTS:")
        adjustments = [
            "Move stop to breakeven after 2% profit",
            "Trail stop by 1.5x ATR from highest point",
            "Tighten stops before major events (earnings, RBI meetings)",
            "Widen stops during high market volatility (VIX >25)"
        ]
        
        for i, adj in enumerate(adjustments, 1):
            print(f"{i}. {adj}")
        
        recommendations['dynamic_adjustments'] = adjustments
        
        # Risk management rules
        print(f"\nRISK MANAGEMENT RULES:")
        risk_rules = [
            "Maximum risk per trade: 2% of capital",
            "Position size = Risk Amount / Stop Loss Distance",
            "Daily loss limit: 6% of capital (max 3 stop outs)",
            "Review and adjust stops weekly based on market regime"
        ]
        
        for i, rule in enumerate(risk_rules, 1):
            print(f"{i}. {rule}")
        
        recommendations['risk_management'] = risk_rules
        
        # Implementation formula
        print(f"\nIMPLEMENTATION FORMULA:")
        print("Stop_Loss_Price = Entry_Price - (1.5 * ATR)")
        print("Position_Size = (Account_Size * 0.02) / (Entry_Price - Stop_Loss_Price)")
        print("Trail_Stop = MAX(Current_Stop, Highest_Price - (1.5 * ATR))")
        
        return recommendations
    
    def create_visualizations(self, brooks_data, methods_comparison):
        """Create stop loss analysis visualizations"""
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        
        # 1. Stop loss distribution
        axes[0,0].hist(brooks_data['stop_loss_pct'], bins=20, alpha=0.7, color='skyblue', edgecolor='black')
        axes[0,0].set_title('Current Stop Loss Distribution')
        axes[0,0].set_xlabel('Stop Loss (%)')
        axes[0,0].set_ylabel('Frequency')
        axes[0,0].axvline(brooks_data['stop_loss_pct'].mean(), color='red', linestyle='--', 
                         label=f'Mean: {brooks_data["stop_loss_pct"].mean():.2f}%')
        axes[0,0].legend()
        
        # 2. ATR vs Stop Loss relationship
        axes[0,1].scatter(brooks_data['ATR'], brooks_data['stop_loss_pct'], alpha=0.6)
        axes[0,1].set_title('ATR vs Stop Loss Relationship')
        axes[0,1].set_xlabel('ATR (₹)')
        axes[0,1].set_ylabel('Stop Loss (%)')
        
        # 3. Risk-Reward vs Stop Loss
        axes[0,2].scatter(brooks_data['stop_loss_pct'], brooks_data['Risk_Reward_Ratio'], alpha=0.6, color='green')
        axes[0,2].set_title('Stop Loss vs Risk-Reward Ratio')
        axes[0,2].set_xlabel('Stop Loss (%)')
        axes[0,2].set_ylabel('Risk-Reward Ratio')
        
        # 4. Stop loss method comparison
        methods = ['Current', 'Fixed 2%', 'Fixed 3%', 'ATR 1.5x']
        avg_stops = [
            brooks_data['stop_loss_pct'].mean(),
            2.0,
            3.0,
            methods_comparison['atr_1_5x_stop'].mean()
        ]
        
        bars = axes[1,0].bar(methods, avg_stops, color=['blue', 'orange', 'green', 'red'], alpha=0.7)
        axes[1,0].set_title('Stop Loss Method Comparison')
        axes[1,0].set_ylabel('Average Stop Loss (%)')
        axes[1,0].tick_params(axis='x', rotation=45)
        
        # Add value labels on bars
        for bar, value in zip(bars, avg_stops):
            axes[1,0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                          f'{value:.2f}%', ha='center', va='bottom')
        
        # 5. ATR distribution
        axes[1,1].hist(methods_comparison['atr_pct'], bins=20, alpha=0.7, color='orange', edgecolor='black')
        axes[1,1].set_title('ATR Distribution')
        axes[1,1].set_xlabel('ATR (%)')
        axes[1,1].set_ylabel('Frequency')
        axes[1,1].axvline(methods_comparison['atr_pct'].mean(), color='red', linestyle='--',
                         label=f'Mean: {methods_comparison["atr_pct"].mean():.2f}%')
        axes[1,1].legend()
        
        # 6. Stop loss efficiency (theoretical)
        stop_ranges = ['0-2%', '2-3%', '3-4%', '4-5%', '5%+']
        efficiency_scores = [85, 75, 65, 55, 45]  # Theoretical efficiency scores
        
        axes[1,2].bar(stop_ranges, efficiency_scores, color='purple', alpha=0.7)
        axes[1,2].set_title('Stop Loss Efficiency (Theoretical)')
        axes[1,2].set_xlabel('Stop Loss Range')
        axes[1,2].set_ylabel('Efficiency Score')
        axes[1,2].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig('/Users/maverick/PycharmProjects/India-TS/ML/results/stop_loss_analysis.png', 
                    dpi=300, bbox_inches='tight')
        plt.show()

def main():
    analyzer = StopLossAnalyzer()
    
    # Load data
    print("Loading Brooks reversal data...")
    brooks_data = analyzer.load_all_brooks_data()
    
    if brooks_data.empty:
        print("No data found!")
        return
    
    # Run analyses
    brooks_data = analyzer.analyze_existing_stop_losses(brooks_data)
    price_analysis = analyzer.analyze_price_movements(brooks_data)
    methods_comparison = analyzer.compare_stop_loss_methods(brooks_data)
    trailing_analysis = analyzer.analyze_dynamic_stops(brooks_data)
    recommendations = analyzer.generate_stop_loss_recommendations(brooks_data, methods_comparison)
    
    # Create visualizations
    analyzer.create_visualizations(brooks_data, methods_comparison)
    
    print(f"\nAnalysis complete! Charts saved to: /Users/maverick/PycharmProjects/India-TS/ML/results/stop_loss_analysis.png")

if __name__ == "__main__":
    main()