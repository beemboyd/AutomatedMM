#!/usr/bin/env python3
"""
Test VSR Momentum Strategy
Demonstrates entry and exit rules with example scenarios
"""

from datetime import datetime, timedelta
from vsr_momentum_exit_rules import VSRMomentumExitRules

def print_separator():
    print("="*80)

def test_entry_criteria():
    """Show entry criteria examples"""
    print_separator()
    print("VSR MOMENTUM ENTRY CRITERIA")
    print_separator()
    
    print("\nMinimum Requirements for Entry:")
    print("- VSR Score: ≥ 80 (indicates strong volume-price relationship)")
    print("- VSR Ratio: ≥ 2.0 (volume is 2x normal)")
    print("- Momentum: 2-10% (not too early, not too extended)")
    print("- Build: Preferably with 📈 indicator")
    
    print("\n✅ GOOD Entry Examples:")
    good_examples = [
        {"ticker": "RAINBOW", "score": 100, "vsr": 11.89, "momentum": 5.7, "build": 10},
        {"ticker": "BORORENEW", "score": 90, "vsr": 3.12, "momentum": 4.3, "build": 0},
        {"ticker": "TCS", "score": 80, "vsr": 2.72, "momentum": 2.5, "build": 10},
    ]
    
    for ex in good_examples:
        priority = ex['score'] + (ex['vsr'] * 10) + (ex['momentum'] * 5) + (10 if ex['build'] > 0 else 0)
        print(f"\n{ex['ticker']}: Score={ex['score']}, VSR={ex['vsr']:.2f}, Mom={ex['momentum']}%, Build={'📈' if ex['build'] else 'No'}")
        print(f"  Priority Score: {priority:.1f}")
    
    print("\n\n❌ BAD Entry Examples:")
    bad_examples = [
        {"ticker": "ABC", "score": 70, "vsr": 1.5, "momentum": 1.0, "reason": "Score too low (<80)"},
        {"ticker": "XYZ", "score": 85, "vsr": 1.8, "momentum": 3.0, "reason": "VSR too low (<2.0)"},
        {"ticker": "PQR", "score": 90, "vsr": 3.5, "momentum": 0.5, "reason": "Momentum too low (<2%)"},
        {"ticker": "LMN", "score": 95, "vsr": 4.0, "momentum": 12.0, "reason": "Too extended (>10%)"},
    ]
    
    for ex in bad_examples:
        print(f"\n{ex['ticker']}: Score={ex['score']}, VSR={ex['vsr']:.2f}, Mom={ex['momentum']}%")
        print(f"  ❌ Rejected: {ex['reason']}")

def test_exit_scenarios():
    """Show exit rule examples"""
    print_separator()
    print("VSR MOMENTUM EXIT SCENARIOS")
    print_separator()
    
    rules = VSRMomentumExitRules()
    
    # Scenario 1: Initial Stop Loss
    print("\n📍 Scenario 1: Initial Stop Loss")
    position1 = {
        'entry_price': 1000,
        'entry_time': datetime.now().isoformat(),
        'peak_price': 1000
    }
    current_price = 980
    stop_loss, reason = rules.calculate_stop_loss(position1, current_price)
    pnl = ((current_price - position1['entry_price']) / position1['entry_price']) * 100
    print(f"Entry: ₹1000, Current: ₹{current_price}, PnL: {pnl:.1f}%")
    print(f"Stop Loss: ₹{stop_loss:.2f} ({reason})")
    
    # Scenario 2: Trailing Stop Activated
    print("\n📍 Scenario 2: Trailing Stop Activated")
    position2 = {
        'entry_price': 1000,
        'entry_time': (datetime.now() - timedelta(minutes=45)).isoformat(),
        'peak_price': 1025
    }
    current_price = 1020
    stop_loss, reason = rules.calculate_stop_loss(position2, current_price)
    pnl = ((current_price - position2['entry_price']) / position2['entry_price']) * 100
    print(f"Entry: ₹1000, Current: ₹{current_price}, Peak: ₹{position2['peak_price']}, PnL: {pnl:.1f}%")
    print(f"Stop Loss: ₹{stop_loss:.2f} ({reason})")
    
    # Scenario 3: Partial Profit Target
    print("\n📍 Scenario 3: Partial Profit Target Hit")
    position3 = {
        'entry_price': 1000,
        'entry_time': (datetime.now() - timedelta(minutes=60)).isoformat(),
        'peak_price': 1050,
        'partial_profit_taken': False
    }
    current_price = 1050
    should_partial, partial_pct, partial_reason = rules.should_take_partial_profit(position3, current_price)
    pnl = ((current_price - position3['entry_price']) / position3['entry_price']) * 100
    print(f"Entry: ₹1000, Current: ₹{current_price}, PnL: {pnl:.1f}%")
    print(f"Partial Profit: {should_partial} - {partial_reason}")
    
    # Scenario 4: Full Exit Target
    print("\n📍 Scenario 4: Full Profit Target")
    position4 = {
        'entry_price': 1000,
        'entry_time': (datetime.now() - timedelta(minutes=90)).isoformat(),
        'peak_price': 1080
    }
    current_price = 1080
    stop_loss, reason = rules.calculate_stop_loss(position4, current_price)
    pnl = ((current_price - position4['entry_price']) / position4['entry_price']) * 100
    print(f"Entry: ₹1000, Current: ₹{current_price}, PnL: {pnl:.1f}%")
    print(f"Exit: {reason}")
    
    # Scenario 5: Time-based Exit
    print("\n📍 Scenario 5: Maximum Hold Time")
    position5 = {
        'entry_price': 1000,
        'entry_time': (datetime.now() - timedelta(minutes=185)).isoformat(),
        'peak_price': 1015
    }
    current_price = 1015
    stop_loss, reason = rules.calculate_stop_loss(position5, current_price)
    print(f"Entry: ₹1000, Current: ₹{current_price}, Time Held: 185 minutes")
    print(f"Exit: {reason}")
    
    # Scenario 6: Momentum Exhaustion
    print("\n📍 Scenario 6: Momentum Exhaustion")
    position6 = {
        'entry_price': 1000,
        'entry_time': (datetime.now() - timedelta(minutes=35)).isoformat(),
        'peak_price': 1003
    }
    current_price = 1003
    stop_loss, reason = rules.calculate_stop_loss(position6, current_price)
    pnl = ((current_price - position6['entry_price']) / position6['entry_price']) * 100
    print(f"Entry: ₹1000, Current: ₹{current_price}, PnL: {pnl:.1f}%, Time: 35 min")
    print(f"Exit: {reason}")

def show_risk_reward_analysis():
    """Show risk-reward calculations"""
    print_separator()
    print("RISK-REWARD ANALYSIS")
    print_separator()
    
    entry_price = 1000
    initial_stop = entry_price * 0.97  # 3% stop
    partial_target = entry_price * 1.05  # 5% partial
    full_target = entry_price * 1.08  # 8% full
    
    print(f"\nFor Entry at ₹{entry_price}:")
    print(f"- Initial Stop Loss: ₹{initial_stop:.2f} (-3.0%)")
    print(f"- Partial Profit (50%): ₹{partial_target:.2f} (+5.0%)")
    print(f"- Full Exit Target: ₹{full_target:.2f} (+8.0%)")
    
    risk = 30  # ₹30 risk per share
    reward_partial = 50  # ₹50 on partial
    reward_full = 80  # ₹80 on full
    
    print(f"\nRisk-Reward Ratios:")
    print(f"- To Partial Target: 1:{reward_partial/risk:.1f}")
    print(f"- To Full Target: 1:{reward_full/risk:.1f}")
    
    print(f"\nExpected Value (assuming 60% win rate):")
    # Scenario: 60% win, 40% loss
    # Winners: 30% hit full target, 30% hit partial only
    expected_value = (0.3 * 80) + (0.3 * 25) - (0.4 * 30)  # 25 is avg of partial exit
    print(f"Expected profit per trade: ₹{expected_value:.2f}")
    print(f"Expected return: {expected_value/1000*100:.2f}%")

def show_position_sizing():
    """Show position sizing examples"""
    print_separator()
    print("POSITION SIZING EXAMPLES")
    print_separator()
    
    account_values = [100000, 500000, 1000000]
    position_size_pct = 2.0
    
    for account_value in account_values:
        print(f"\nAccount Value: ₹{account_value:,}")
        position_value = account_value * (position_size_pct / 100)
        print(f"Position Size (2%): ₹{position_value:,.0f}")
        
        # Example stocks
        stocks = [
            {"name": "Low Price", "price": 200},
            {"name": "Mid Price", "price": 1000},
            {"name": "High Price", "price": 5000}
        ]
        
        for stock in stocks:
            quantity = int(position_value / stock['price'])
            actual_value = quantity * stock['price']
            print(f"  {stock['name']} @ ₹{stock['price']}: {quantity} shares = ₹{actual_value:,}")

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("VSR MOMENTUM STRATEGY - ENTRY & EXIT RULES DEMONSTRATION")
    print("="*80)
    
    test_entry_criteria()
    print("\n")
    test_exit_scenarios()
    print("\n")
    show_risk_reward_analysis()
    print("\n")
    show_position_sizing()
    
    print("\n" + "="*80)
    print("KEY TAKEAWAYS:")
    print("="*80)
    print("1. Entry: High VSR (≥2.0) + High Score (≥80) + Moderate Momentum (2-10%)")
    print("2. Stop Loss: 3% initial, then trailing at 1.5% from peak after 2% profit")
    print("3. Targets: 50% exit at 5%, full exit at 8%")
    print("4. Time Limit: Maximum 3 hours to avoid overnight risk")
    print("5. Position Size: 2% of capital per trade, max 5 positions")
    print("="*80)

if __name__ == "__main__":
    main()