#!/usr/bin/env python3
"""
Kelly Criterion P&L Tracker
Tracks actual performance vs Kelly predictions for parameter tuning
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import os
from pathlib import Path

class KellyPnLTracker:
    """Track and analyze P&L for Kelly Criterion tuning"""
    
    def __init__(self):
        self.data_dir = os.path.join(os.path.dirname(__file__), 'kelly_tracking')
        Path(self.data_dir).mkdir(exist_ok=True)
        self.trades_file = os.path.join(self.data_dir, 'kelly_trades.csv')
        self.analysis_file = os.path.join(self.data_dir, 'kelly_analysis.json')
        
    def log_trade(self, trade_data):
        """
        Log a trade with Kelly predictions and actual results
        
        trade_data should include:
        - date, symbol, direction, regime
        - kelly_percent, win_probability, win_loss_ratio, expected_value
        - position_size, entry_price, exit_price, stop_loss
        - actual_pnl, actual_pnl_percent, win_loss (1 for win, 0 for loss)
        """
        df = pd.DataFrame([trade_data])
        
        if os.path.exists(self.trades_file):
            existing_df = pd.read_csv(self.trades_file)
            df = pd.concat([existing_df, df], ignore_index=True)
        
        df.to_csv(self.trades_file, index=False)
        print(f"Trade logged: {trade_data['symbol']} - {'Win' if trade_data['win_loss'] else 'Loss'}")
        
    def analyze_performance(self, days=30):
        """Analyze Kelly performance over specified period"""
        if not os.path.exists(self.trades_file):
            print("No trades to analyze")
            return None
            
        df = pd.read_csv(self.trades_file)
        df['date'] = pd.to_datetime(df['date'])
        
        # Filter for recent period
        cutoff_date = datetime.now() - timedelta(days=days)
        df = df[df['date'] >= cutoff_date]
        
        if len(df) == 0:
            print(f"No trades in last {days} days")
            return None
        
        analysis = {}
        
        # Overall statistics
        analysis['overall'] = {
            'total_trades': len(df),
            'win_rate': df['win_loss'].mean(),
            'avg_win': df[df['win_loss'] == 1]['actual_pnl_percent'].mean() if len(df[df['win_loss'] == 1]) > 0 else 0,
            'avg_loss': abs(df[df['win_loss'] == 0]['actual_pnl_percent'].mean()) if len(df[df['win_loss'] == 0]) > 0 else 0,
            'actual_win_loss_ratio': 0,
            'total_pnl': df['actual_pnl'].sum(),
            'sharpe_ratio': self._calculate_sharpe(df['actual_pnl_percent']),
            'max_drawdown': self._calculate_max_drawdown(df['actual_pnl'].cumsum())
        }
        
        # Calculate actual win/loss ratio
        if analysis['overall']['avg_loss'] > 0:
            analysis['overall']['actual_win_loss_ratio'] = (
                analysis['overall']['avg_win'] / analysis['overall']['avg_loss']
            )
        
        # Analysis by regime
        analysis['by_regime'] = {}
        for regime in df['regime'].unique():
            regime_df = df[df['regime'] == regime]
            analysis['by_regime'][regime] = {
                'trades': len(regime_df),
                'actual_win_rate': regime_df['win_loss'].mean(),
                'predicted_win_rate': regime_df['win_probability'].mean(),
                'win_rate_diff': regime_df['win_loss'].mean() - regime_df['win_probability'].mean(),
                'avg_kelly_percent': regime_df['kelly_percent'].mean(),
                'total_pnl': regime_df['actual_pnl'].sum(),
                'pnl_per_trade': regime_df['actual_pnl'].mean()
            }
        
        # Kelly accuracy analysis
        analysis['kelly_accuracy'] = self._analyze_kelly_accuracy(df)
        
        # Save analysis
        with open(self.analysis_file, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        return analysis
    
    def _calculate_sharpe(self, returns, risk_free_rate=0.0):
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0
        excess_returns = returns - risk_free_rate
        return np.sqrt(252) * excess_returns.mean() / excess_returns.std() if excess_returns.std() > 0 else 0
    
    def _calculate_max_drawdown(self, cumulative_pnl):
        """Calculate maximum drawdown"""
        running_max = cumulative_pnl.expanding().max()
        drawdown = (cumulative_pnl - running_max) / running_max.replace(0, 1)
        return drawdown.min()
    
    def _analyze_kelly_accuracy(self, df):
        """Analyze how well Kelly predictions match reality"""
        # Group by Kelly percentage buckets
        df['kelly_bucket'] = pd.cut(df['kelly_percent'], 
                                    bins=[0, 5, 10, 15, 20, 100],
                                    labels=['0-5%', '5-10%', '10-15%', '15-20%', '20%+'])
        
        accuracy = {}
        for bucket in df['kelly_bucket'].cat.categories:
            bucket_df = df[df['kelly_bucket'] == bucket]
            if len(bucket_df) > 0:
                accuracy[bucket] = {
                    'trades': len(bucket_df),
                    'actual_win_rate': bucket_df['win_loss'].mean(),
                    'predicted_win_rate': bucket_df['win_probability'].mean(),
                    'avg_pnl_percent': bucket_df['actual_pnl_percent'].mean(),
                    'predicted_ev': bucket_df['expected_value'].mean(),
                    'actual_ev': bucket_df['actual_pnl_percent'].mean()
                }
        
        return accuracy
    
    def generate_tuning_recommendations(self):
        """Generate recommendations for tuning Kelly parameters"""
        analysis = self.analyze_performance()
        if not analysis:
            return None
        
        recommendations = []
        
        # Overall win rate adjustment
        actual_wr = analysis['overall']['win_rate']
        if actual_wr < 0.45:
            recommendations.append({
                'parameter': 'base_win_rate',
                'action': 'reduce',
                'reason': f'Actual win rate ({actual_wr:.1%}) is below 45%',
                'suggested_reduction': 0.1
            })
        
        # Win/loss ratio adjustment
        actual_wl = analysis['overall']['actual_win_loss_ratio']
        if actual_wl < 1.0:
            recommendations.append({
                'parameter': 'win_loss_ratio',
                'action': 'reduce',
                'reason': f'Actual W/L ratio ({actual_wl:.2f}) is below 1.0',
                'suggested_value': actual_wl
            })
        
        # Regime-specific adjustments
        for regime, stats in analysis['by_regime'].items():
            if stats['trades'] >= 10:  # Minimum sample size
                wr_diff = stats['win_rate_diff']
                if abs(wr_diff) > 0.1:
                    recommendations.append({
                        'parameter': f'{regime}_base_win_rate',
                        'action': 'adjust',
                        'reason': f'{regime} win rate off by {wr_diff:.1%}',
                        'current_predicted': stats['predicted_win_rate'],
                        'actual': stats['actual_win_rate']
                    })
        
        # Safety factor adjustment based on drawdown
        max_dd = abs(analysis['overall']['max_drawdown'])
        if max_dd > 0.20:  # 20% drawdown
            recommendations.append({
                'parameter': 'kelly_safety_factor',
                'action': 'reduce',
                'reason': f'Max drawdown ({max_dd:.1%}) exceeds 20%',
                'suggested_value': 0.15
            })
        
        return recommendations
    
    def export_report(self):
        """Export detailed P&L report"""
        analysis = self.analyze_performance()
        if not analysis:
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = os.path.join(self.data_dir, f'kelly_pnl_report_{timestamp}.md')
        
        with open(report_file, 'w') as f:
            f.write("# Kelly Criterion P&L Analysis Report\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## Overall Performance\n")
            f.write(f"- Total Trades: {analysis['overall']['total_trades']}\n")
            f.write(f"- Win Rate: {analysis['overall']['win_rate']:.1%}\n")
            f.write(f"- Win/Loss Ratio: {analysis['overall']['actual_win_loss_ratio']:.2f}\n")
            f.write(f"- Total P&L: ₹{analysis['overall']['total_pnl']:,.2f}\n")
            f.write(f"- Sharpe Ratio: {analysis['overall']['sharpe_ratio']:.2f}\n")
            f.write(f"- Max Drawdown: {analysis['overall']['max_drawdown']:.1%}\n\n")
            
            f.write("## Performance by Regime\n")
            for regime, stats in analysis['by_regime'].items():
                f.write(f"\n### {regime}\n")
                f.write(f"- Trades: {stats['trades']}\n")
                f.write(f"- Actual Win Rate: {stats['actual_win_rate']:.1%}\n")
                f.write(f"- Predicted Win Rate: {stats['predicted_win_rate']:.1%}\n")
                f.write(f"- Difference: {stats['win_rate_diff']:+.1%}\n")
                f.write(f"- Avg Kelly %: {stats['avg_kelly_percent']:.1f}%\n")
                f.write(f"- P&L per Trade: ₹{stats['pnl_per_trade']:,.2f}\n")
            
            f.write("\n## Kelly Accuracy by Size\n")
            for bucket, stats in analysis['kelly_accuracy'].items():
                f.write(f"\n### {bucket}\n")
                f.write(f"- Trades: {stats['trades']}\n")
                f.write(f"- Actual Win Rate: {stats['actual_win_rate']:.1%}\n")
                f.write(f"- Predicted Win Rate: {stats['predicted_win_rate']:.1%}\n")
                f.write(f"- Actual EV: {stats['actual_ev']:.1%}\n")
                f.write(f"- Predicted EV: {stats['predicted_ev']:.1%}\n")
            
            # Add recommendations
            recommendations = self.generate_tuning_recommendations()
            if recommendations:
                f.write("\n## Tuning Recommendations\n")
                for i, rec in enumerate(recommendations, 1):
                    f.write(f"\n{i}. **{rec['parameter']}** - {rec['action']}\n")
                    f.write(f"   - Reason: {rec['reason']}\n")
                    if 'suggested_value' in rec:
                        f.write(f"   - Suggested value: {rec['suggested_value']}\n")
        
        print(f"Report saved to: {report_file}")
        return report_file


# Example usage
if __name__ == "__main__":
    tracker = KellyPnLTracker()
    
    # Example: Log a trade
    sample_trade = {
        'date': datetime.now(),
        'symbol': 'RELIANCE',
        'direction': 'long',
        'regime': 'uptrend',
        'kelly_percent': 12.5,
        'win_probability': 0.65,
        'win_loss_ratio': 1.5,
        'expected_value': 0.475,
        'position_size': 125000,
        'entry_price': 2500,
        'exit_price': 2600,
        'stop_loss': 2450,
        'actual_pnl': 5000,
        'actual_pnl_percent': 4.0,
        'win_loss': 1  # 1 for win, 0 for loss
    }
    
    # tracker.log_trade(sample_trade)
    
    # Analyze performance
    # analysis = tracker.analyze_performance()
    # if analysis:
    #     print(json.dumps(analysis, indent=2))
    
    # Generate report
    # tracker.export_report()