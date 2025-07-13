"""
Volume-Price Anomaly Analysis Summary and Implementation Guide
=============================================================
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json
import os

def generate_summary_report():
    """Generate comprehensive summary of volume-price anomaly findings"""
    
    summary = {
        "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "key_findings": {
            "exhaustion_patterns": {
                "high_volume_low_momentum": {
                    "definition": "Volume > 3x average with momentum < 5%",
                    "risk_level": "HIGH",
                    "action": "Consider immediate exit or very tight stop loss",
                    "examples": ["JAGSNPHARM (Vol: 7.5x, Mom: 4.7%)", "ANANDRATHI (Vol: 6.7x, Mom: 4.6%)"]
                },
                "volume_efficiency_breakdown": {
                    "definition": "Volume efficiency < 1.0 (momentum/volume ratio)",
                    "risk_level": "MEDIUM-HIGH",
                    "action": "Tighten stop loss, monitor closely",
                    "threshold": 1.0
                },
                "narrow_range_high_volume": {
                    "definition": "Volume > 2x with price spread < 2%",
                    "risk_level": "MEDIUM",
                    "action": "Watch for rejection, consider partial exit",
                    "characteristics": "Often precedes sharp reversals"
                }
            },
            "actionable_metrics": {
                "exhaustion_score": {
                    "calculation": "Sum of: Price_Rejection*2 + Volume_Exhaustion*3 + Narrow_Range*1",
                    "thresholds": {
                        "0-2": "Low risk - Continue holding",
                        "3": "Medium risk - Tighten stops",
                        "4+": "High risk - Consider exit"
                    }
                },
                "volume_price_ratio": {
                    "calculation": "Volume_Ratio / Price_Spread_Percentage",
                    "interpretation": "Higher values indicate volume not translating to price movement"
                }
            },
            "identified_patterns": {
                "price_rejection": {
                    "count": 224,
                    "percentage": "2.6% of all scans",
                    "success_rate": "21.9% led to stop loss within 5 days"
                },
                "volume_exhaustion": {
                    "count": 1160,
                    "percentage": "13.2% of all scans",
                    "characteristics": "Average time to reversal: 1.9 days"
                }
            }
        },
        "implementation_guide": {
            "immediate_actions": [
                "1. Add exhaustion_score calculation to daily scanner",
                "2. Flag tickers with score >= 3 for review",
                "3. Auto-tighten stops for score >= 4"
            ],
            "monitoring_rules": {
                "real_time": [
                    "Track volume spikes intraday",
                    "Compare current volume ratio to 20-day average",
                    "Alert if volume > 3x with price movement < 2%"
                ],
                "end_of_day": [
                    "Calculate exhaustion score for all positions",
                    "Generate high-risk candidate list",
                    "Update stop losses based on risk level"
                ]
            },
            "stop_loss_adjustments": {
                "exhaustion_score_0_2": "Standard ATR-based stop",
                "exhaustion_score_3": "Tighten to 0.75x ATR",
                "exhaustion_score_4_plus": "Tighten to 0.5x ATR or consider exit"
            }
        },
        "recent_high_risk_candidates": [
            {
                "ticker": "JAGSNPHARM",
                "volume_ratio": 7.52,
                "momentum_5d": 4.73,
                "volume_efficiency": 0.63,
                "risk_assessment": "HIGH - Volume exhaustion pattern"
            },
            {
                "ticker": "ANANDRATHI",
                "volume_ratio": 6.74,
                "momentum_5d": 4.59,
                "volume_efficiency": 0.68,
                "risk_assessment": "HIGH - Low efficiency with high volume"
            },
            {
                "ticker": "GLENMARK",
                "volume_ratio": 8.27,
                "momentum_5d": 18.83,
                "volume_efficiency": 2.28,
                "risk_assessment": "MEDIUM - High volume but decent momentum"
            }
        ],
        "recommended_exit_rules": {
            "rule_1": {
                "name": "Volume Exhaustion Exit",
                "condition": "Volume > 3x AND Momentum < 5%",
                "action": "Exit 50% position immediately, tight stop on remainder"
            },
            "rule_2": {
                "name": "Efficiency Breakdown Exit",
                "condition": "Volume Efficiency < 0.5 for 2 consecutive scans",
                "action": "Exit full position"
            },
            "rule_3": {
                "name": "Narrow Range Rejection",
                "condition": "Volume > 2x AND Daily Range < 1.5% AND Close near day's low",
                "action": "Exit at next day's open"
            }
        }
    }
    
    # Save summary
    output_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/volume_analysis"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save as JSON
    json_file = os.path.join(output_dir, "volume_anomaly_summary.json")
    with open(json_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Create readable report
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("VOLUME-PRICE ANOMALY ANALYSIS - IMPLEMENTATION SUMMARY")
    report_lines.append("=" * 80)
    report_lines.append(f"Generated: {summary['analysis_date']}")
    report_lines.append("")
    
    report_lines.append("KEY EXHAUSTION PATTERNS IDENTIFIED:")
    report_lines.append("-" * 50)
    for pattern_name, pattern_data in summary['key_findings']['exhaustion_patterns'].items():
        report_lines.append(f"\n{pattern_name.upper().replace('_', ' ')}:")
        report_lines.append(f"  Definition: {pattern_data['definition']}")
        report_lines.append(f"  Risk Level: {pattern_data['risk_level']}")
        report_lines.append(f"  Action: {pattern_data['action']}")
    
    report_lines.append("\n\nRECOMMENDED EXIT RULES:")
    report_lines.append("-" * 50)
    for rule_id, rule in summary['recommended_exit_rules'].items():
        report_lines.append(f"\n{rule['name']}:")
        report_lines.append(f"  Condition: {rule['condition']}")
        report_lines.append(f"  Action: {rule['action']}")
    
    report_lines.append("\n\nCURRENT HIGH-RISK CANDIDATES:")
    report_lines.append("-" * 50)
    for candidate in summary['recent_high_risk_candidates']:
        report_lines.append(f"\n{candidate['ticker']}:")
        report_lines.append(f"  Volume Ratio: {candidate['volume_ratio']:.2f}x")
        report_lines.append(f"  Momentum: {candidate['momentum_5d']:.2f}%")
        report_lines.append(f"  Efficiency: {candidate['volume_efficiency']:.2f}")
        report_lines.append(f"  Assessment: {candidate['risk_assessment']}")
    
    report_lines.append("\n\nIMPLEMENTATION STEPS:")
    report_lines.append("-" * 50)
    for i, action in enumerate(summary['implementation_guide']['immediate_actions'], 1):
        report_lines.append(action)
    
    # Save text report
    report_text = "\n".join(report_lines)
    text_file = os.path.join(output_dir, "volume_anomaly_implementation.txt")
    with open(text_file, 'w') as f:
        f.write(report_text)
    
    print(report_text)
    print(f"\nFiles saved:")
    print(f"  - {json_file}")
    print(f"  - {text_file}")
    
    return summary

def create_exit_signal_code():
    """Generate code snippet for implementing volume-based exit signals"""
    
    code_snippet = '''
def calculate_exhaustion_score(ticker_data):
    """Calculate exhaustion score for a ticker based on volume-price anomalies"""
    score = 0
    
    # Price Rejection: High volume but low momentum
    if ticker_data['volume_ratio'] > ticker_data['volume_ratio_75th_percentile'] and \
       ticker_data['momentum_5d'] < ticker_data['momentum_25th_percentile']:
        score += 2
    
    # Volume Exhaustion: Very high volume with weak price action
    if ticker_data['volume_ratio'] > 3 and ticker_data['momentum_5d'] < 5:
        score += 3
    
    # Narrow Range High Volume
    price_spread_pct = (ticker_data['atr'] / ticker_data['close']) * 100
    if ticker_data['volume_ratio'] > 2 and price_spread_pct < 2:
        score += 1
    
    return score

def should_exit_position(ticker, current_data, position_data):
    """Determine if position should be exited based on volume anomalies"""
    
    # Calculate metrics
    volume_efficiency = current_data['momentum_5d'] / current_data['volume_ratio']
    exhaustion_score = calculate_exhaustion_score(current_data)
    
    # Exit conditions
    exit_reasons = []
    
    # Rule 1: Volume Exhaustion
    if current_data['volume_ratio'] > 3 and current_data['momentum_5d'] < 5:
        exit_reasons.append("Volume exhaustion detected")
    
    # Rule 2: Low efficiency
    if volume_efficiency < 0.5:
        exit_reasons.append("Volume efficiency breakdown")
    
    # Rule 3: High exhaustion score
    if exhaustion_score >= 4:
        exit_reasons.append(f"High exhaustion score: {exhaustion_score}")
    
    # Rule 4: Narrow range rejection (intraday check)
    if current_data['volume_ratio'] > 2:
        daily_range_pct = ((current_data['high'] - current_data['low']) / current_data['close']) * 100
        close_position_pct = (current_data['close'] - current_data['low']) / (current_data['high'] - current_data['low'])
        
        if daily_range_pct < 1.5 and close_position_pct < 0.3:  # Close in bottom 30% of range
            exit_reasons.append("Narrow range rejection pattern")
    
    return len(exit_reasons) > 0, exit_reasons

def adjust_stop_loss_by_exhaustion(ticker, current_stop_loss, atr, exhaustion_score):
    """Adjust stop loss based on exhaustion score"""
    
    if exhaustion_score == 0:
        # No adjustment needed
        return current_stop_loss
    elif exhaustion_score <= 2:
        # Minor tightening
        return current_stop_loss + (0.25 * atr)
    elif exhaustion_score == 3:
        # Moderate tightening
        return current_stop_loss + (0.5 * atr)
    else:  # exhaustion_score >= 4
        # Aggressive tightening
        return current_stop_loss + (0.75 * atr)
'''
    
    # Save code snippet
    output_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/volume_analysis"
    code_file = os.path.join(output_dir, "volume_exit_signals.py")
    with open(code_file, 'w') as f:
        f.write(code_snippet)
    
    print(f"\nExit signal code saved to: {code_file}")

if __name__ == "__main__":
    # Generate summary report
    summary = generate_summary_report()
    
    # Create implementation code
    create_exit_signal_code()
    
    print("\n✅ Volume-Price Anomaly Analysis Complete!")
    print("Review the generated files for implementation details.")