#!/usr/bin/env python3
"""
Performance Analytics for VSR Paper Trading
Analyzes entry timing, slice effectiveness, and overall performance
"""

import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple

class VSRPerformanceAnalyzer:
    def __init__(self, db_path: str = "data/paper_trades.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        
    def analyze_entry_timing(self) -> Dict:
        """Analyze the effectiveness of entry timing"""
        query = '''
            SELECT t.*, p.pnl, p.current_price, p.avg_price
            FROM trades t
            JOIN positions p ON t.ticker = p.ticker
            WHERE t.slice_number = 1
            ORDER BY t.timestamp
        '''
        
        df = pd.read_sql_query(query, self.conn)
        if df.empty:
            return {}
        
        # Calculate entry effectiveness
        df['entry_hour'] = pd.to_datetime(df['timestamp']).dt.hour
        df['entry_effectiveness'] = ((df['current_price'] - df['price']) / df['price']) * 100
        
        # Best entry times
        hourly_performance = df.groupby('entry_hour').agg({
            'entry_effectiveness': ['mean', 'count', 'std']
        }).round(2)
        
        # VSR correlation with performance
        vsr_bins = [0, 3, 5, 10, 100]
        vsr_labels = ['Low (0-3)', 'Medium (3-5)', 'High (5-10)', 'Very High (10+)']
        df['vsr_category'] = pd.cut(df['vsr'], bins=vsr_bins, labels=vsr_labels)
        
        vsr_performance = df.groupby('vsr_category').agg({
            'entry_effectiveness': ['mean', 'count'],
            'pnl': 'mean'
        }).round(2)
        
        return {
            'hourly_performance': hourly_performance.to_dict(),
            'vsr_performance': vsr_performance.to_dict(),
            'best_entry_hour': hourly_performance['entry_effectiveness']['mean'].idxmax(),
            'avg_entry_effectiveness': df['entry_effectiveness'].mean()
        }
    
    def analyze_slice_effectiveness(self) -> Dict:
        """Analyze how well the slicing strategy works"""
        query = '''
            SELECT ticker, slice_number, total_slices, quantity, price, vsr, momentum_score
            FROM trades
            WHERE status = 'EXECUTED'
            ORDER BY ticker, slice_number
        '''
        
        trades_df = pd.read_sql_query(query, self.conn)
        if trades_df.empty:
            return {}
        
        # Calculate average price by slice number
        slice_analysis = trades_df.groupby('slice_number').agg({
            'price': ['mean', 'std'],
            'quantity': 'sum',
            'vsr': 'mean'
        }).round(2)
        
        # Calculate price improvement from slicing
        ticker_groups = trades_df.groupby('ticker')
        price_improvements = []
        
        for ticker, group in ticker_groups:
            if len(group) > 1:
                first_price = group.iloc[0]['price']
                avg_price = (group['price'] * group['quantity']).sum() / group['quantity'].sum()
                improvement = ((first_price - avg_price) / first_price) * 100
                price_improvements.append({
                    'ticker': ticker,
                    'first_price': first_price,
                    'avg_price': avg_price,
                    'improvement_pct': improvement
                })
        
        avg_improvement = np.mean([p['improvement_pct'] for p in price_improvements]) if price_improvements else 0
        
        return {
            'slice_analysis': slice_analysis.to_dict(),
            'avg_price_improvement': avg_improvement,
            'price_improvements': price_improvements[:10]  # Top 10
        }
    
    def analyze_overall_performance(self) -> Dict:
        """Analyze overall trading performance"""
        # Get all positions
        positions_df = pd.read_sql_query("SELECT * FROM positions", self.conn)
        if positions_df.empty:
            return {}
        
        # Calculate metrics
        total_trades = len(positions_df)
        profitable_trades = (positions_df['pnl'] > 0).sum()
        losing_trades = (positions_df['pnl'] < 0).sum()
        
        win_rate = (profitable_trades / total_trades) * 100 if total_trades > 0 else 0
        
        avg_win = positions_df[positions_df['pnl'] > 0]['pnl'].mean() if profitable_trades > 0 else 0
        avg_loss = positions_df[positions_df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
        
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        # Calculate Sharpe ratio (simplified)
        returns = positions_df['pnl'] / 10000  # Normalized returns
        sharpe_ratio = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
        
        # Best and worst trades
        best_trades = positions_df.nlargest(5, 'pnl')[['ticker', 'pnl', 'vsr', 'momentum_score']]
        worst_trades = positions_df.nsmallest(5, 'pnl')[['ticker', 'pnl', 'vsr', 'momentum_score']]
        
        return {
            'total_trades': total_trades,
            'profitable_trades': profitable_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            'total_pnl': positions_df['pnl'].sum(),
            'best_trades': best_trades.to_dict('records'),
            'worst_trades': worst_trades.to_dict('records')
        }
    
    def generate_report(self, save_path: str = "performance_report.txt"):
        """Generate comprehensive performance report"""
        print("\n📊 VSR PAPER TRADING PERFORMANCE REPORT")
        print("=" * 50)
        
        # Entry timing analysis
        entry_analysis = self.analyze_entry_timing()
        if entry_analysis:
            print("\n📍 ENTRY TIMING ANALYSIS:")
            print(f"Best Entry Hour: {entry_analysis.get('best_entry_hour', 'N/A')}")
            print(f"Avg Entry Effectiveness: {entry_analysis.get('avg_entry_effectiveness', 0):.2f}%")
        
        # Slice effectiveness
        slice_analysis = self.analyze_slice_effectiveness()
        if slice_analysis:
            print("\n🔪 SLICE EFFECTIVENESS:")
            print(f"Avg Price Improvement from Slicing: {slice_analysis.get('avg_price_improvement', 0):.2f}%")
        
        # Overall performance
        performance = self.analyze_overall_performance()
        if performance:
            print("\n📈 OVERALL PERFORMANCE:")
            print(f"Total Trades: {performance['total_trades']}")
            print(f"Win Rate: {performance['win_rate']:.1f}%")
            print(f"Profit Factor: {performance['profit_factor']:.2f}")
            print(f"Sharpe Ratio: {performance['sharpe_ratio']:.2f}")
            print(f"Total P&L: ₹{performance['total_pnl']:,.0f}")
            
            print("\n🏆 BEST TRADES:")
            for trade in performance['best_trades']:
                print(f"  {trade['ticker']}: ₹{trade['pnl']:,.0f} (VSR: {trade['vsr']:.1f})")
            
            print("\n📉 WORST TRADES:")
            for trade in performance['worst_trades']:
                print(f"  {trade['ticker']}: ₹{trade['pnl']:,.0f} (VSR: {trade['vsr']:.1f})")
        
        # Save to file
        with open(save_path, 'w') as f:
            f.write(f"VSR Paper Trading Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n")
            f.write(json.dumps({
                'entry_analysis': entry_analysis,
                'slice_analysis': slice_analysis,
                'performance': performance
            }, indent=2))
    
    def plot_performance_charts(self):
        """Generate performance visualization charts"""
        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('VSR Paper Trading Performance Analysis', fontsize=16)
        
        # 1. P&L Distribution
        positions_df = pd.read_sql_query("SELECT pnl FROM positions WHERE pnl IS NOT NULL", self.conn)
        if not positions_df.empty:
            axes[0, 0].hist(positions_df['pnl'], bins=20, color='skyblue', edgecolor='black')
            axes[0, 0].axvline(x=0, color='red', linestyle='--')
            axes[0, 0].set_title('P&L Distribution')
            axes[0, 0].set_xlabel('P&L (₹)')
            axes[0, 0].set_ylabel('Frequency')
        
        # 2. VSR vs Performance
        vsr_perf_df = pd.read_sql_query(
            "SELECT vsr, pnl FROM positions WHERE vsr IS NOT NULL AND pnl IS NOT NULL", 
            self.conn
        )
        if not vsr_perf_df.empty:
            axes[0, 1].scatter(vsr_perf_df['vsr'], vsr_perf_df['pnl'], alpha=0.6)
            axes[0, 1].set_title('VSR vs P&L')
            axes[0, 1].set_xlabel('VSR')
            axes[0, 1].set_ylabel('P&L (₹)')
        
        # 3. Hourly Performance
        hourly_df = pd.read_sql_query(
            '''SELECT strftime('%H', timestamp) as hour, 
                      AVG((current_price - avg_price) / avg_price * 100) as avg_return
               FROM trades t
               JOIN positions p ON t.ticker = p.ticker
               WHERE t.slice_number = 1
               GROUP BY hour''', 
            self.conn
        )
        if not hourly_df.empty:
            hourly_df['hour'] = hourly_df['hour'].astype(int)
            axes[1, 0].bar(hourly_df['hour'], hourly_df['avg_return'])
            axes[1, 0].set_title('Average Returns by Entry Hour')
            axes[1, 0].set_xlabel('Hour of Day')
            axes[1, 0].set_ylabel('Avg Return (%)')
        
        # 4. Cumulative P&L
        cum_pnl_df = pd.read_sql_query(
            "SELECT timestamp, pnl FROM trades ORDER BY timestamp", 
            self.conn
        )
        if not cum_pnl_df.empty:
            cum_pnl_df['cum_pnl'] = cum_pnl_df['pnl'].cumsum()
            axes[1, 1].plot(range(len(cum_pnl_df)), cum_pnl_df['cum_pnl'])
            axes[1, 1].set_title('Cumulative P&L')
            axes[1, 1].set_xlabel('Trade Number')
            axes[1, 1].set_ylabel('Cumulative P&L (₹)')
        
        plt.tight_layout()
        plt.savefig('vsr_performance_charts.png')
        print("\n📈 Performance charts saved to vsr_performance_charts.png")

if __name__ == "__main__":
    import json
    
    analyzer = VSRPerformanceAnalyzer()
    analyzer.generate_report()
    
    # Generate charts if we have data
    try:
        analyzer.plot_performance_charts()
    except Exception as e:
        print(f"Could not generate charts: {e}")