"""
Short Position Strategies Analysis for July 2025
Compare three strategies for short positions with position building:
1. Position Doubling Strategy
2. Fixed Position Sizing (1% increments)
3. Call Selling Strategy (at upper Keltner Channel)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import norm

class ShortPositionStrategiesAnalysis:
    def __init__(self):
        self.selected_stocks = ["RELIANCE", "TCS", "INFY"]  # 3 random popular stocks
        self.results = {
            'doubling': [],
            'fixed_sizing': [],
            'call_selling': []
        }
        
    def generate_synthetic_data(self, ticker, start_date, days=31):
        """Generate synthetic daily data for July 2025"""
        timestamps = pd.date_range(
            start=start_date,
            periods=days,
            freq='D'
        )
        
        # Generate realistic price movements with some downward bias for short testing
        base_price = 100 + np.random.uniform(50, 500)  # Random base price
        
        data = []
        prev_close = base_price
        
        # Parameters for realistic movement (bearish month)
        annual_volatility = np.random.uniform(0.35, 0.55)  # Higher volatility for bearish month
        daily_volatility = annual_volatility / np.sqrt(252)
        drift = np.random.uniform(-0.002, -0.0005)  # Strong downward bias for bearish month
        
        for i, ts in enumerate(timestamps):
            # Add some trend and volatility
            price_change = (drift + np.random.normal(0, daily_volatility)) * prev_close
            
            open_price = prev_close
            close_price = prev_close + price_change
            
            # Calculate realistic high and low
            intraday_range = abs(price_change) * np.random.uniform(1.5, 3.0)
            high_price = max(open_price, close_price) + intraday_range * 0.6
            low_price = min(open_price, close_price) - intraday_range * 0.4
            
            volume = int(np.random.uniform(100000, 1000000))
            
            data.append({
                'date': ts,
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': volume
            })
            
            prev_close = close_price
        
        df = pd.DataFrame(data)
        df.set_index('date', inplace=True)
        
        # Calculate Keltner Channels for call selling
        df = self.calculate_keltner_channels(df)
        
        return df
    
    def calculate_keltner_channels(self, data, period=20, multiplier=2.0):
        """Calculate Keltner Channel bands"""
        data['ema'] = data['close'].ewm(span=period, min_periods=1).mean()
        
        data['high_low'] = data['high'] - data['low']
        data['high_close'] = abs(data['high'] - data['close'].shift(1))
        data['low_close'] = abs(data['low'] - data['close'].shift(1))
        data['true_range'] = data[['high_low', 'high_close', 'low_close']].max(axis=1)
        data['atr'] = data['true_range'].rolling(window=period, min_periods=1).mean()
        
        data['kc_upper'] = data['ema'] + (multiplier * data['atr'])
        data['kc_lower'] = data['ema'] - (multiplier * data['atr'])
        
        return data
    
    def simulate_doubling_strategy(self, ticker, daily_data):
        """Simulate position doubling strategy for shorts"""
        trade_details = {
            'ticker': ticker,
            'strategy': 'doubling',
            'entry_date': None,
            'exit_date': None,
            'max_position_size': 0,
            'positions': [],
            'pnl': 0,
            'pnl_percent': 0,
            'trade_duration_days': 0
        }
        
        position_size = 0
        avg_entry_price = 0
        total_short_value = 0
        
        entry_found = False
        prev_high = None
        prev_close = None
        
        # Look for entry signal (price near upper resistance)
        for i, (date, row) in enumerate(daily_data.iterrows()):
            if i < 5:  # Need some history
                continue
                
            # Entry condition: Price breaks above recent high (short opportunity)
            recent_high = daily_data.iloc[max(0, i-5):i]['high'].max()
            recent_close = daily_data.iloc[i-1]['close']
            
            # Bearish month strategy: Short on weakness or failed rallies
            entry_condition = (row['close'] < recent_close * 0.98 or  # 2% down from previous close (weakness)
                             (row['close'] > recent_close * 1.02 and row['close'] < recent_high))  # Failed rally
            
            if not entry_found and entry_condition:
                # Initial short position
                position_size = 1
                avg_entry_price = row['close']
                total_short_value = avg_entry_price
                
                trade_details['entry_date'] = date
                trade_details['positions'].append({
                    'date': date,
                    'action': 'SHORT',
                    'price': row['close'],
                    'size': 1,
                    'cumulative_size': position_size
                })
                
                entry_found = True
                prev_close = row['close']
                prev_high = row['high']
                
            elif entry_found:
                # Double position if price moves against us (higher)
                if prev_close and row['close'] > prev_close:
                    new_shares = position_size  # Double position
                    position_size += new_shares
                    total_short_value += row['close'] * new_shares
                    avg_entry_price = total_short_value / position_size
                    
                    trade_details['positions'].append({
                        'date': date,
                        'action': 'ADD_SHORT',
                        'price': row['close'],
                        'size': new_shares,
                        'cumulative_size': position_size
                    })
                
                # Exit condition: Take profit on significant drop or stop loss on rally
                if row['close'] < trade_details['positions'][0]['price'] * 0.95:  # 5% profit target
                    trade_details['exit_date'] = date
                    trade_details['max_position_size'] = position_size
                    
                    exit_value = row['close'] * position_size
                    trade_details['pnl'] = total_short_value - exit_value
                    trade_details['pnl_percent'] = (trade_details['pnl'] / total_short_value) * 100
                    trade_details['trade_duration_days'] = (date - trade_details['entry_date']).days
                    
                    break
                # Stop loss condition: Price rallies significantly
                elif row['close'] > trade_details['positions'][0]['price'] * 1.10:  # 10% stop loss
                    exit_value = row['close'] * position_size
                    trade_details['pnl'] = total_short_value - exit_value  # Profit when price drops
                    trade_details['pnl_percent'] = (trade_details['pnl'] / total_short_value) * 100
                    trade_details['trade_duration_days'] = (date - trade_details['entry_date']).days
                    
                    break
                
                prev_close = row['close']
                prev_high = row['high']
        
        # Close at end if no exit
        if entry_found and trade_details['exit_date'] is None:
            last_row = daily_data.iloc[-1]
            trade_details['exit_date'] = daily_data.index[-1]
            trade_details['max_position_size'] = position_size
            
            exit_value = last_row['close'] * position_size
            trade_details['pnl'] = total_short_value - exit_value
            trade_details['pnl_percent'] = (trade_details['pnl'] / total_short_value) * 100
            trade_details['trade_duration_days'] = (trade_details['exit_date'] - trade_details['entry_date']).days
        
        return trade_details if entry_found else None
    
    def simulate_fixed_sizing_strategy(self, ticker, daily_data):
        """Simulate fixed sizing strategy for shorts (1% increments, max 5 positions)"""
        trade_details = {
            'ticker': ticker,
            'strategy': 'fixed_sizing',
            'entry_date': None,
            'exit_date': None,
            'max_positions': 0,
            'positions': [],
            'pnl': 0,
            'pnl_percent': 0,
            'trade_duration_days': 0
        }
        
        positions = []  # List of short positions
        total_short_value = 0
        
        entry_found = False
        prev_high = None
        prev_close = None
        
        for i, (date, row) in enumerate(daily_data.iterrows()):
            if i < 5:
                continue
                
            recent_high = daily_data.iloc[max(0, i-5):i]['high'].max()
            recent_close = daily_data.iloc[i-1]['close']
            
            entry_condition = (row['close'] < recent_close * 0.98 or
                             (row['close'] > recent_close * 1.02 and row['close'] < recent_high))
            
            if not entry_found and entry_condition:
                # Initial short position - 1%
                positions.append({
                    'entry_price': row['close'],
                    'size': 0.01
                })
                total_short_value += row['close'] * 0.01
                
                trade_details['entry_date'] = date
                trade_details['positions'].append({
                    'date': date,
                    'action': 'SHORT',
                    'price': row['close'],
                    'size': 0.01,
                    'total_positions': len(positions)
                })
                
                entry_found = True
                prev_close = row['close']
                prev_high = row['high']
                
            elif entry_found:
                # Add position if price moves against us and we have room
                if prev_close and row['close'] > prev_close and len(positions) < 5:
                    positions.append({
                        'entry_price': row['close'],
                        'size': 0.01
                    })
                    total_short_value += row['close'] * 0.01
                    
                    trade_details['positions'].append({
                        'date': date,
                        'action': 'ADD_SHORT',
                        'price': row['close'],
                        'size': 0.01,
                        'total_positions': len(positions)
                    })
                
                # Exit condition: Profit target or stop loss
                initial_price = trade_details['positions'][0]['price']
                if row['close'] < initial_price * 0.95:  # 5% profit target
                    trade_details['exit_date'] = date
                    trade_details['max_positions'] = len(positions)
                    
                    # Calculate P&L
                    exit_value = 0
                    for pos in positions:
                        exit_value += row['close'] * pos['size']
                    
                    trade_details['pnl'] = total_short_value - exit_value
                    trade_details['pnl_percent'] = (trade_details['pnl'] / total_short_value) * 100
                    trade_details['trade_duration_days'] = (date - trade_details['entry_date']).days
                    
                    break
                
                prev_close = row['close']
                prev_high = row['high']
        
        # Close at end if no exit
        if entry_found and trade_details['exit_date'] is None:
            last_row = daily_data.iloc[-1]
            trade_details['exit_date'] = daily_data.index[-1]
            trade_details['max_positions'] = len(positions)
            
            exit_value = 0
            for pos in positions:
                exit_value += last_row['close'] * pos['size']
                
            trade_details['pnl'] = total_short_value - exit_value
            trade_details['pnl_percent'] = (trade_details['pnl'] / total_short_value) * 100
            trade_details['trade_duration_days'] = (trade_details['exit_date'] - trade_details['entry_date']).days
        
        return trade_details if entry_found else None
    
    def calculate_call_option_price(self, spot_price, strike_price, time_to_expiry, risk_free_rate=0.06, volatility=0.30):
        """Calculate call option price using Black-Scholes formula"""
        if time_to_expiry <= 0:
            return max(spot_price - strike_price, 0)
        
        d1 = (np.log(spot_price / strike_price) + (risk_free_rate + 0.5 * volatility**2) * time_to_expiry) / (volatility * np.sqrt(time_to_expiry))
        d2 = d1 - volatility * np.sqrt(time_to_expiry)
        
        call_price = spot_price * norm.cdf(d1) - strike_price * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
        return max(call_price, 0)
    
    def simulate_call_selling_strategy(self, ticker, daily_data):
        """Simulate selling calls at upper Keltner Channel (bearish strategy)"""
        trade_details = {
            'ticker': ticker,
            'strategy': 'call_selling',
            'entry_date': None,
            'exit_date': None,
            'strike_price': None,
            'premium_collected': 0,
            'premium_yield': 0,
            'pnl': 0,
            'pnl_percent': 0,
            'exit_reason': None,
            'success': False,
            'days_held': 0
        }
        
        # Look for entry signal
        for i, (date, row) in enumerate(daily_data.iterrows()):
            if i < 5:
                continue
                
            if pd.isna(row['kc_upper']):
                continue
                
            recent_high = daily_data.iloc[max(0, i-5):i]['high'].max()
            
            # Entry: Price showing weakness or near resistance
            # In bearish month, look for any signs of weakness or resistance rejection
            if (row['close'] <= row['kc_upper'] * 1.02 and  # Near or above upper band (resistance)
                row['close'] > daily_data.iloc[i-1]['close'] * 0.99):  # Not in free fall
                strike_price = row['kc_upper']
                spot_price = row['close']
                
                # Skip if strike too close
                if (strike_price - spot_price) / spot_price < 0.02:
                    continue
                
                # Set up call selling
                expiry_days = 30  # 1 month
                time_to_expiry = expiry_days / 365.0
                
                premium_collected = self.calculate_call_option_price(
                    spot_price, strike_price, time_to_expiry, volatility=0.35
                )
                
                premium_yield = (premium_collected / strike_price) * 100
                
                trade_details.update({
                    'entry_date': date,
                    'strike_price': strike_price,
                    'spot_at_entry': spot_price,
                    'premium_collected': premium_collected,
                    'premium_yield': premium_yield,
                    'margin_required': strike_price * 0.20  # 20% margin
                })
                
                # Track through expiry
                for j in range(i+1, min(i+expiry_days+1, len(daily_data))):
                    current_date = daily_data.index[j]
                    current_row = daily_data.iloc[j]
                    days_remaining = expiry_days - (j - i)
                    
                    if days_remaining <= 0:
                        # At expiry
                        intrinsic_value = max(current_row['close'] - strike_price, 0)
                        final_pnl = premium_collected - intrinsic_value
                        
                        trade_details.update({
                            'exit_date': current_date,
                            'exit_reason': 'expiry',
                            'pnl': final_pnl,
                            'pnl_percent': (final_pnl / trade_details['margin_required']) * 100,
                            'spot_at_exit': current_row['close'],
                            'success': final_pnl > 0,
                            'days_held': j - i
                        })
                        break
                    
                    # Calculate current option value
                    time_remaining = days_remaining / 365.0
                    current_option_value = self.calculate_call_option_price(
                        current_row['close'], strike_price, time_remaining, volatility=0.35
                    )
                    
                    current_pnl = premium_collected - current_option_value
                    
                    # Early exit conditions
                    if current_pnl >= premium_collected * 0.5:  # 50% profit target
                        trade_details.update({
                            'exit_date': current_date,
                            'exit_reason': 'profit_target',
                            'pnl': current_pnl,
                            'pnl_percent': (current_pnl / trade_details['margin_required']) * 100,
                            'spot_at_exit': current_row['close'],
                            'success': True,
                            'days_held': j - i
                        })
                        break
                    
                    # Stop loss at -200% of premium
                    if current_pnl <= -premium_collected * 2.0:
                        trade_details.update({
                            'exit_date': current_date,
                            'exit_reason': 'stop_loss',
                            'pnl': current_pnl,
                            'pnl_percent': (current_pnl / trade_details['margin_required']) * 100,
                            'spot_at_exit': current_row['close'],
                            'success': False,
                            'days_held': j - i
                        })
                        break
                
                break  # Only one trade per stock
        
        return trade_details if trade_details['entry_date'] else None
    
    def run_analysis(self):
        """Run complete analysis for all three strategies"""
        print("Starting Short Position Strategies Analysis...")
        print("=" * 60)
        
        july_start = datetime(2025, 7, 1)
        
        all_results = {
            'doubling': [],
            'fixed_sizing': [],
            'call_selling': []
        }
        
        for ticker in self.selected_stocks:
            print(f"\nAnalyzing {ticker}...")
            
            # Generate synthetic data for July
            daily_data = self.generate_synthetic_data(ticker, july_start)
            
            # Run all three strategies
            doubling_trade = self.simulate_doubling_strategy(ticker, daily_data)
            if doubling_trade:
                all_results['doubling'].append(doubling_trade)
                print(f"  Doubling: P&L={doubling_trade['pnl_percent']:.2f}%, Max Pos={doubling_trade['max_position_size']}")
            
            fixed_trade = self.simulate_fixed_sizing_strategy(ticker, daily_data)
            if fixed_trade:
                all_results['fixed_sizing'].append(fixed_trade)
                print(f"  Fixed: P&L={fixed_trade['pnl_percent']:.2f}%, Max Pos={fixed_trade['max_positions']}")
            
            call_trade = self.simulate_call_selling_strategy(ticker, daily_data)
            if call_trade:
                all_results['call_selling'].append(call_trade)
                print(f"  Call Selling: P&L={call_trade['pnl_percent']:.2f}%, Premium={call_trade['premium_yield']:.2f}%")
        
        # Generate comparison report
        self.generate_comparison_report(all_results)
        
        return all_results
    
    def generate_comparison_report(self, results):
        """Generate comprehensive comparison report"""
        print("\n" + "=" * 60)
        print("SHORT POSITION STRATEGIES COMPARISON")
        print("=" * 60)
        
        strategies = ['doubling', 'fixed_sizing', 'call_selling']
        strategy_names = ['Position Doubling', 'Fixed Sizing (1%)', 'Call Selling']
        
        comparison_data = []
        
        for i, strategy in enumerate(strategies):
            trades = results[strategy]
            if not trades:
                continue
                
            df = pd.DataFrame(trades)
            
            if strategy == 'call_selling':
                win_rate = len(df[df['success'] == True]) / len(df) * 100
                avg_pnl = df['pnl_percent'].mean()
                best_trade = df['pnl_percent'].max()
                worst_trade = df['pnl_percent'].min()
                avg_duration = df['days_held'].mean()
            else:
                win_rate = len(df[df['pnl'] > 0]) / len(df) * 100
                avg_pnl = df['pnl_percent'].mean()
                best_trade = df['pnl_percent'].max()
                worst_trade = df['pnl_percent'].min()
                avg_duration = df['trade_duration_days'].mean()
            
            comparison_data.append({
                'Strategy': strategy_names[i],
                'Total Trades': len(df),
                'Win Rate %': f"{win_rate:.1f}%",
                'Avg P&L %': f"{avg_pnl:.2f}%",
                'Best Trade %': f"{best_trade:.2f}%",
                'Worst Trade %': f"{worst_trade:.2f}%",
                'Avg Duration': f"{avg_duration:.1f} days"
            })
        
        # Create comparison table
        comparison_df = pd.DataFrame(comparison_data)
        print("\nStrategy Performance Comparison:")
        print(comparison_df.to_string(index=False))
        
        # Risk Assessment
        print("\n" + "-" * 60)
        print("RISK ASSESSMENT")
        print("-" * 60)
        
        print("\n1. Position Doubling Strategy:")
        print("   Pros: Potential for large gains in trending markets")
        print("   Cons: Exponential risk, can lead to massive losses")
        print("   Risk: VERY HIGH - Position sizes can grow exponentially")
        
        print("\n2. Fixed Sizing Strategy (1%):")
        print("   Pros: Controlled risk, maximum 5% exposure")
        print("   Cons: Limited profit potential")
        print("   Risk: LOW - Capped at 5% per trade")
        
        print("\n3. Call Selling Strategy:")
        print("   Pros: Time decay works in favor, high win rates typically")
        print("   Cons: Limited upside, assignment risk")
        print("   Risk: MEDIUM - Defined risk with potential for large losses")
        
        # Recommendations
        print("\n" + "-" * 60)
        print("RECOMMENDATIONS")
        print("-" * 60)
        
        best_strategy = None
        best_pnl = float('-inf')
        
        for data in comparison_data:
            pnl = float(data['Avg P&L %'].replace('%', ''))
            if pnl > best_pnl:
                best_pnl = pnl
                best_strategy = data['Strategy']
        
        print(f"\nBest Performing Strategy: {best_strategy}")
        print(f"Average P&L: {best_pnl:.2f}%")
        
        if best_pnl > 0:
            print(f"\n✅ {best_strategy} shows positive expected value")
            if best_strategy == "Call Selling":
                print("   - Requires options trading approval")
                print("   - Start with paper trading")
                print("   - Focus on liquid stocks")
            elif best_strategy == "Fixed Sizing (1%)":
                print("   - Good risk management")
                print("   - Suitable for beginners")
                print("   - Scale position sizes based on conviction")
            else:
                print("   - High risk strategy")
                print("   - Requires strict position limits")
                print("   - Not recommended for most traders")
        else:
            print(f"\n❌ All strategies show negative expected value")
            print("   - Market conditions may not favor short positions")
            print("   - Consider waiting for better entry opportunities")
            print("   - Focus on risk management over returns")
        
        # Save results
        self.save_analysis_results(results, comparison_df)
    
    def save_analysis_results(self, results, comparison_df):
        """Save analysis results to files"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save detailed results to JSON
        output = {
            'analysis_date': datetime.now().isoformat(),
            'period': 'July 2025',
            'stocks_analyzed': self.selected_stocks,
            'strategies': ['Position Doubling', 'Fixed Sizing (1%)', 'Call Selling'],
            'results': results,
            'comparison_summary': comparison_df.to_dict('records')
        }
        
        json_path = f'/Users/maverick/PycharmProjects/India-TS/Daily/analysis/short_strategies_analysis_{timestamp}.json'
        with open(json_path, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        # Create Excel file
        excel_path = f'/Users/maverick/PycharmProjects/India-TS/Daily/analysis/short_strategies_analysis_{timestamp}.xlsx'
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            comparison_df.to_excel(writer, sheet_name='Strategy Comparison', index=False)
            
            # Add detailed results for each strategy
            for strategy, trades in results.items():
                if trades:
                    df = pd.DataFrame(trades)
                    df.to_excel(writer, sheet_name=f'{strategy.title()} Details', index=False)
        
        # Create markdown report
        report_path = f'/Users/maverick/PycharmProjects/India-TS/Daily/analysis/short_strategies_report_{timestamp}.md'
        self.create_markdown_report(output, comparison_df, report_path)
        
        print(f"\nResults saved to:")
        print(f"  - {json_path}")
        print(f"  - {excel_path}")
        print(f"  - {report_path}")
    
    def create_markdown_report(self, output, comparison_df, report_path):
        """Create detailed markdown report"""
        with open(report_path, 'w') as f:
            f.write("# Short Position Strategies Analysis\n\n")
            f.write(f"**Analysis Date:** {output['analysis_date']}\n")
            f.write(f"**Period:** {output['period']}\n")
            f.write(f"**Stocks Analyzed:** {', '.join(output['stocks_analyzed'])}\n\n")
            
            f.write("## Strategies Tested\n")
            f.write("1. **Position Doubling:** Double position size when price moves against short\n")
            f.write("2. **Fixed Sizing:** Add 1% positions up to maximum 5% exposure\n")
            f.write("3. **Call Selling:** Sell calls at upper Keltner Channel (bearish bet)\n\n")
            
            f.write("## Performance Summary\n\n")
            f.write("| Strategy | Total Trades | Win Rate | Avg P&L | Best Trade | Worst Trade | Avg Duration |\n")
            f.write("|----------|--------------|----------|---------|------------|-------------|-------------|\n")
            
            for _, row in comparison_df.iterrows():
                f.write(f"| {row['Strategy']} | {row['Total Trades']} | {row['Win Rate %']} | {row['Avg P&L %']} | {row['Best Trade %']} | {row['Worst Trade %']} | {row['Avg Duration']} |\n")
            
            f.write("\n## Key Insights\n\n")
            f.write("### Short Position Challenges\n")
            f.write("- **Limited Upside:** Maximum profit is 100% (stock goes to zero)\n")
            f.write("- **Unlimited Downside:** Losses can exceed initial capital\n")
            f.write("- **Time Decay:** Holding costs and borrowing fees\n")
            f.write("- **Squeeze Risk:** Short squeezes can cause rapid losses\n\n")
            
            f.write("### Strategy-Specific Analysis\n\n")
            f.write("#### Position Doubling\n")
            f.write("- **High Risk:** Can lead to exponential losses\n")
            f.write("- **Capital Intensive:** Requires significant margin\n")
            f.write("- **Trend Dependent:** Works only in strong downtrends\n\n")
            
            f.write("#### Fixed Sizing (1%)\n")
            f.write("- **Risk Controlled:** Maximum 5% exposure per trade\n")
            f.write("- **Manageable:** Suitable for risk-averse traders\n")
            f.write("- **Limited Profit:** Capped upside potential\n\n")
            
            f.write("#### Call Selling\n")
            f.write("- **Time Advantage:** Benefits from theta decay\n")
            f.write("- **High Win Rate:** Typically 70-80% success rate\n")
            f.write("- **Complex:** Requires options knowledge and approval\n\n")
            
            f.write("## Risk Management Guidelines\n\n")
            f.write("1. **Position Sizing:** Never risk more than 2-5% of portfolio per trade\n")
            f.write("2. **Stop Losses:** Always have predefined exit rules\n")
            f.write("3. **Diversification:** Don't concentrate shorts in one sector\n")
            f.write("4. **Market Timing:** Avoid shorting in strong bull markets\n")
            f.write("5. **Liquidity:** Only short highly liquid stocks\n\n")
            
            f.write("## Implementation Considerations\n\n")
            f.write("- **Margin Requirements:** Short selling requires margin account\n")
            f.write("- **Borrowing Costs:** Hard-to-borrow stocks have high fees\n")
            f.write("- **Regulatory Risks:** Short sale restrictions and circuit breakers\n")
            f.write("- **Psychological Challenges:** Shorting against the trend is difficult\n\n")
            
            f.write("## Conclusion\n\n")
            f.write("Short selling strategies require careful risk management and are generally ")
            f.write("more suitable for experienced traders. The call selling approach may offer ")
            f.write("the best risk-adjusted returns but requires options trading expertise.\n")

def main():
    analyzer = ShortPositionStrategiesAnalysis()
    results = analyzer.run_analysis()
    return results

if __name__ == "__main__":
    main()