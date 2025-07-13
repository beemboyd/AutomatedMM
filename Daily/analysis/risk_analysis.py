#!/usr/bin/env python
"""
Risk Analysis Script - Calculate portfolio risk based on stop-loss values
Analyzes worst-case scenario for each user's portfolio using SL_watchdog logs
"""

import os
import re
import json
import argparse
import logging
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import pandas as pd

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PortfolioRiskAnalyzer:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.logs_dir = os.path.join(base_dir, "logs")
        self.orders_dir = os.path.join(base_dir, "Current_Orders")
        self.users = ["Mom", "Sai", "Som", "Su"]
        
    def parse_stop_loss_from_log(self, user: str) -> Dict[str, float]:
        """Parse the latest stop-loss values from SL_watchdog log"""
        stop_losses = {}
        log_file = os.path.join(self.logs_dir, user, f"SL_watchdog_{user}.log")
        
        if not os.path.exists(log_file):
            logger.warning(f"Log file not found for {user}: {log_file}")
            return stop_losses
            
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                
            # Parse from end to get latest values
            for line in reversed(lines):
                # Pattern 1: "TICKER: ATR Stop Loss Updated - ... Stop Loss: ₹XXX.XX"
                match1 = re.search(r'(\w+): ATR Stop Loss Updated.*Stop Loss: ₹([\d,]+\.?\d*)', line)
                if match1:
                    ticker = match1.group(1)
                    stop_loss = float(match1.group(2).replace(',', ''))
                    if ticker not in stop_losses:
                        stop_losses[ticker] = stop_loss
                        
                # Pattern 2: "TICKER: DAILY HIGH TRAILING STOP UPDATED - New: ₹XXX.XX"
                match2 = re.search(r'(\w+): DAILY HIGH TRAILING STOP UPDATED - New: ₹([\d,]+\.?\d*)', line)
                if match2:
                    ticker = match2.group(1)
                    stop_loss = float(match2.group(2).replace(',', ''))
                    if ticker not in stop_losses:
                        stop_losses[ticker] = stop_loss
                        
        except Exception as e:
            logger.error(f"Error parsing log for {user}: {e}")
            
        return stop_losses
    
    def parse_positions_from_log(self, user: str) -> Dict[str, Dict]:
        """Parse current positions and quantities from SL_watchdog log"""
        positions = {}
        log_file = os.path.join(self.logs_dir, user, f"SL_watchdog_{user}.log")
        
        if not os.path.exists(log_file):
            return positions
            
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                
            # Search for the most recent position data
            # Look for lines with position info pattern
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i]
                
                # Pattern: "🟢/🔴 TICKER: Qty=XXX, Avg=₹XXX.XX, LTP=₹XXX.XX"
                if ('🟢' in line or '🔴' in line) and 'Qty=' in line and 'Avg=₹' in line:
                    match = re.search(r'[🟢🔴]\s+(\w+):\s+Qty=(\d+),\s+Avg=₹([\d,]+\.?\d*),\s+LTP=₹([\d,]+\.?\d*)', line)
                    if match:
                        ticker = match.group(1)
                        # Only add if we haven't seen this ticker yet (we're going backwards)
                        if ticker not in positions:
                            positions[ticker] = {
                                'quantity': int(match.group(2)),
                                'avg_price': float(match.group(3).replace(',', '')),
                                'ltp': float(match.group(4).replace(',', ''))
                            }
                
                # Stop when we've gone back far enough (e.g., found a reasonable number of positions)
                # or reached the beginning of today's data
                if len(positions) > 50 or (i < len(lines) - 10000 and len(positions) > 0):
                    break
                    
            logger.debug(f"Found {len(positions)} positions for {user}")
                    
        except Exception as e:
            logger.error(f"Error parsing positions for {user}: {e}")
            
        return positions
    
    def calculate_risk(self, positions: Dict, stop_losses: Dict) -> Dict:
        """Calculate risk for each position and total portfolio risk"""
        risk_analysis = {
            'positions': {},
            'total_investment': 0,
            'total_risk_amount': 0,
            'total_risk_percent': 0,
            'positions_without_sl': []
        }
        
        for ticker, pos_data in positions.items():
            qty = pos_data['quantity']
            avg_price = pos_data['avg_price']
            ltp = pos_data['ltp']
            investment = qty * avg_price
            current_value = qty * ltp
            
            risk_analysis['total_investment'] += investment
            
            if ticker in stop_losses:
                sl_price = stop_losses[ticker]
                risk_per_share = ltp - sl_price
                total_risk = risk_per_share * qty
                risk_percent = (risk_per_share / ltp) * 100
                
                risk_analysis['positions'][ticker] = {
                    'quantity': qty,
                    'avg_price': avg_price,
                    'ltp': ltp,
                    'stop_loss': sl_price,
                    'investment': investment,
                    'current_value': current_value,
                    'risk_per_share': risk_per_share,
                    'total_risk': total_risk,
                    'risk_percent': risk_percent
                }
                
                risk_analysis['total_risk_amount'] += total_risk
            else:
                risk_analysis['positions_without_sl'].append(ticker)
                
        if risk_analysis['total_investment'] > 0:
            risk_analysis['total_risk_percent'] = (risk_analysis['total_risk_amount'] / risk_analysis['total_investment']) * 100
            
        return risk_analysis
    
    def generate_report(self, all_user_risks: Dict) -> None:
        """Generate formatted risk analysis report"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print("\n" + "="*80)
        print(f"PORTFOLIO RISK ANALYSIS REPORT - {timestamp}")
        print("="*80)
        print("\nWORST CASE SCENARIO ANALYSIS (If all positions hit stop-loss)")
        print("="*80)
        
        grand_total_investment = 0
        grand_total_risk = 0
        
        for user, risk_data in all_user_risks.items():
            print(f"\n\n{'='*60}")
            print(f"USER: {user}")
            print(f"{'='*60}")
            
            if not risk_data['positions']:
                print("No positions found with stop-loss data")
                continue
                
            # Sort positions by risk amount (descending)
            sorted_positions = sorted(
                risk_data['positions'].items(),
                key=lambda x: x[1]['total_risk'],
                reverse=True
            )
            
            print(f"\nTotal Investment: ₹{risk_data['total_investment']:,.2f}")
            print(f"Total Risk Amount: ₹{risk_data['total_risk_amount']:,.2f}")
            print(f"Total Risk Percent: {risk_data['total_risk_percent']:.2f}%")
            
            if risk_data['positions_without_sl']:
                print(f"\n⚠️  Positions without stop-loss: {', '.join(risk_data['positions_without_sl'])}")
            
            print(f"\n{'Ticker':<12} {'Qty':>8} {'LTP':>10} {'SL':>10} {'Risk/Share':>12} {'Total Risk':>15} {'Risk %':>8}")
            print("-"*95)
            
            for ticker, pos in sorted_positions[:20]:  # Show top 20 risky positions
                print(f"{ticker:<12} {pos['quantity']:>8,} "
                      f"₹{pos['ltp']:>9,.2f} ₹{pos['stop_loss']:>9,.2f} "
                      f"₹{pos['risk_per_share']:>11,.2f} ₹{pos['total_risk']:>14,.2f} "
                      f"{pos['risk_percent']:>7.2f}%")
            
            if len(sorted_positions) > 20:
                print(f"\n... and {len(sorted_positions) - 20} more positions")
            
            grand_total_investment += risk_data['total_investment']
            grand_total_risk += risk_data['total_risk_amount']
        
        # Summary
        print(f"\n\n{'='*80}")
        print("GRAND TOTAL SUMMARY (All Users)")
        print(f"{'='*80}")
        print(f"Total Investment: ₹{grand_total_investment:,.2f}")
        print(f"Total Risk Amount: ₹{grand_total_risk:,.2f}")
        if grand_total_investment > 0:
            print(f"Total Risk Percent: {(grand_total_risk/grand_total_investment)*100:.2f}%")
        else:
            print("Total Risk Percent: N/A (No investment)")
        print(f"{'='*80}\n")
        
        # Save to file
        self.save_report_to_file(all_user_risks, timestamp)
        
    def save_report_to_file(self, all_user_risks: Dict, timestamp: str) -> None:
        """Save detailed report to Excel file"""
        reports_dir = os.path.join(self.base_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        
        filename = os.path.join(reports_dir, f"risk_analysis_{timestamp.replace(':', '-').replace(' ', '_')}.xlsx")
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = []
            for user, risk_data in all_user_risks.items():
                summary_data.append({
                    'User': user,
                    'Total_Investment': risk_data['total_investment'],
                    'Total_Risk_Amount': risk_data['total_risk_amount'],
                    'Total_Risk_Percent': risk_data['total_risk_percent'],
                    'Positions_Count': len(risk_data['positions']),
                    'Positions_Without_SL': len(risk_data['positions_without_sl'])
                })
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Individual user sheets
            for user, risk_data in all_user_risks.items():
                if risk_data['positions']:
                    positions_list = []
                    for ticker, pos in risk_data['positions'].items():
                        positions_list.append({
                            'Ticker': ticker,
                            'Quantity': pos['quantity'],
                            'Avg_Price': pos['avg_price'],
                            'LTP': pos['ltp'],
                            'Stop_Loss': pos['stop_loss'],
                            'Investment': pos['investment'],
                            'Current_Value': pos['current_value'],
                            'Risk_Per_Share': pos['risk_per_share'],
                            'Total_Risk': pos['total_risk'],
                            'Risk_Percent': pos['risk_percent']
                        })
                    
                    user_df = pd.DataFrame(positions_list)
                    user_df = user_df.sort_values('Total_Risk', ascending=False)
                    user_df.to_excel(writer, sheet_name=user, index=False)
        
        print(f"\nDetailed report saved to: {filename}")
    
    def run_analysis(self) -> None:
        """Main method to run the complete risk analysis"""
        all_user_risks = {}
        
        for user in self.users:
            logger.info(f"Analyzing risk for {user}")
            
            # Parse stop losses
            stop_losses = self.parse_stop_loss_from_log(user)
            logger.info(f"Found {len(stop_losses)} stop-loss values for {user}")
            
            # Parse positions
            positions = self.parse_positions_from_log(user)
            logger.info(f"Found {len(positions)} positions for {user}")
            
            # Calculate risk
            risk_analysis = self.calculate_risk(positions, stop_losses)
            all_user_risks[user] = risk_analysis
            
        # Generate report
        self.generate_report(all_user_risks)


def main():
    parser = argparse.ArgumentParser(description="Portfolio Risk Analysis based on Stop-Loss values")
    parser.add_argument("--base-dir", default="/Users/maverick/PycharmProjects/India-TS/Daily",
                        help="Base directory for India-TS Daily")
    
    args = parser.parse_args()
    
    analyzer = PortfolioRiskAnalyzer(args.base_dir)
    analyzer.run_analysis()


if __name__ == "__main__":
    main()