#!/usr/bin/env python
"""
Script to apply VSR modifications to SL_watchdog.py
"""

import os
import shutil
from datetime import datetime

def apply_vsr_modifications():
    """Apply VSR modifications to SL_watchdog.py"""
    
    # File paths
    original_file = "SL_watchdog.py"
    backup_file = f"SL_watchdog_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
    
    # Create backup
    print(f"Creating backup: {backup_file}")
    shutil.copy2(original_file, backup_file)
    
    # Read the original file
    with open(original_file, 'r') as f:
        lines = f.readlines()
    
    # Find insertion points and modify
    modified_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Add numpy import after other imports
        if line.strip().startswith("import") and "pandas" in line:
            modified_lines.append(line)
            modified_lines.append("import numpy as np\n")
            i += 1
            continue
        
        # Add VSR attributes after sma20_hourly_data initialization
        if "self.sma20_hourly_data = {}" in line:
            modified_lines.append(line)
            modified_lines.append("\n")
            modified_lines.append("        # VSR tracking data\n")
            modified_lines.append("        self.vsr_data = {}  # ticker -> {'entry_vsr': value, 'current_vsr': value, 'vsr_history': [], 'last_hourly_check': datetime}\n")
            modified_lines.append("        self.hourly_candles = {}  # ticker -> list of hourly candles for VSR calculation\n")
            i += 1
            continue
        
        # Add last_vsr_check after last_position_sync
        if "self.last_position_sync = 0" in line:
            modified_lines.append(line)
            modified_lines.append("        self.last_vsr_check = 0  # Track last VSR check time\n")
            i += 1
            continue
        
        # Update the logging message
        if '"ATR-BASED TRAILING STOP LOSS ENABLED"' in line:
            modified_lines.append(line.replace("ATR-BASED TRAILING STOP LOSS ENABLED", 
                                              "ATR-BASED TRAILING STOP LOSS WITH VSR MONITORING ENABLED"))
            i += 1
            continue
        
        # Add VSR logging after trailing stop feature explanation
        if '"- Profits are protected while still allowing for volatility"' in line:
            modified_lines.append(line)
            modified_lines.append('        self.logger.info("")\n')
            modified_lines.append('        self.logger.info("VSR-BASED EXIT RULES (Hourly):")\n')
            modified_lines.append('        self.logger.info("- Exit if hourly VSR drops < 50% of entry VSR")\n')
            modified_lines.append('        self.logger.info("- Exit if position shows -2% loss")\n')
            i += 1
            continue
        
        # Add VSR checks in check_atr_stop_loss method
        if "# SMA20 violation checks are now only done at 2:30 PM IST" in line:
            # Insert VSR checks before this comment
            modified_lines.append("\n")
            modified_lines.append("        # Check VSR conditions (hourly)\n")
            modified_lines.append("        vsr_signal = self.check_vsr_conditions(ticker)\n")
            modified_lines.append("        if vsr_signal:\n")
            modified_lines.append("            # Queue order for VSR-based exit\n")
            modified_lines.append("            self.queue_order(\n")
            modified_lines.append("                ticker,\n")
            modified_lines.append("                expected_quantity,\n")
            modified_lines.append('                "SELL",\n')
            modified_lines.append('                f"VSR_EXIT: {vsr_signal[\'reason\']}",\n')
            modified_lines.append("                current_price\n")
            modified_lines.append("            )\n")
            modified_lines.append("            return\n")
            modified_lines.append("\n")
            modified_lines.append("        # Check -2% loss threshold\n")
            modified_lines.append("        loss_signal = self.check_loss_threshold(ticker, current_price)\n")
            modified_lines.append("        if loss_signal:\n")
            modified_lines.append("            # Queue order for loss threshold exit\n")
            modified_lines.append("            self.queue_order(\n")
            modified_lines.append("                ticker,\n")
            modified_lines.append("                expected_quantity,\n")
            modified_lines.append('                "SELL",\n')
            modified_lines.append('                f"LOSS_EXIT: {loss_signal[\'reason\']}",\n')
            modified_lines.append("                current_price\n")
            modified_lines.append("            )\n")
            modified_lines.append("            return\n")
            modified_lines.append("\n")
            modified_lines.append(line)
            i += 1
            continue
        
        # Default: keep the line as is
        modified_lines.append(line)
        i += 1
    
    # Find where to insert the new methods (after get_instrument_token method)
    insert_index = -1
    for i, line in enumerate(modified_lines):
        if "def remove_position_from_tracking(self, ticker):" in line:
            # Go back to find the end of the previous method
            j = i - 1
            while j > 0 and not (modified_lines[j].strip() == "" and modified_lines[j-1].strip() != ""):
                j -= 1
            insert_index = j
            break
    
    if insert_index > 0:
        # Insert the new VSR methods
        vsr_methods = '''
    def calculate_vsr(self, high, low, volume):
        """Calculate Volume Spread Ratio"""
        spread = high - low
        if spread > 0:
            return volume / spread
        return 0

    def fetch_hourly_data(self, ticker):
        """Fetch hourly candle data for VSR calculation"""
        try:
            instrument_token = self.get_instrument_token(ticker)
            if not instrument_token:
                return None
            
            # Get last 24 hours of hourly data
            to_date = datetime.now()
            from_date = to_date - timedelta(days=1)
            
            historical_data = self.kite.historical_data(
                instrument_token,
                from_date,
                to_date,
                '60minute'
            )
            
            if historical_data:
                # Store in hourly candles cache
                self.hourly_candles[ticker] = historical_data
                return historical_data
            
        except Exception as e:
            self.logger.error(f"Error fetching hourly data for {ticker}: {e}")
        
        return None

    def check_vsr_conditions(self, ticker):
        """Check VSR-based exit conditions on hourly timeframe"""
        try:
            # Only check once per hour
            current_time = datetime.now()
            if ticker in self.vsr_data:
                last_check = self.vsr_data[ticker].get('last_hourly_check')
                if last_check and (current_time - last_check).total_seconds() < 3600:
                    return None
            
            # Fetch latest hourly data
            hourly_data = self.fetch_hourly_data(ticker)
            if not hourly_data or len(hourly_data) < 2:
                return None
            
            # Get the latest complete hourly candle
            latest_candle = hourly_data[-1]
            current_vsr = self.calculate_vsr(
                latest_candle['high'],
                latest_candle['low'],
                latest_candle['volume']
            )
            
            # Initialize VSR data if not exists
            if ticker not in self.vsr_data:
                # Use first candle as entry VSR (or calculate average of recent candles)
                entry_vsr = current_vsr
                if len(hourly_data) >= 20:
                    # Calculate 20-period average VSR
                    vsr_values = [self.calculate_vsr(c['high'], c['low'], c['volume']) for c in hourly_data[-20:]]
                    entry_vsr = np.mean([v for v in vsr_values if v > 0])
                
                self.vsr_data[ticker] = {
                    'entry_vsr': entry_vsr,
                    'current_vsr': current_vsr,
                    'vsr_history': [current_vsr],
                    'last_hourly_check': current_time,
                    'avg_vsr': entry_vsr
                }
                
                self.logger.info(f"{ticker}: VSR monitoring initialized - Entry VSR: {entry_vsr:.0f}, Current VSR: {current_vsr:.0f}")
                return None
            
            # Update VSR data
            vsr_info = self.vsr_data[ticker]
            vsr_info['current_vsr'] = current_vsr
            vsr_info['vsr_history'].append(current_vsr)
            vsr_info['last_hourly_check'] = current_time
            
            # Keep only last 24 hours of history
            if len(vsr_info['vsr_history']) > 24:
                vsr_info['vsr_history'] = vsr_info['vsr_history'][-24:]
            
            # Check VSR deterioration
            avg_vsr = vsr_info['avg_vsr']
            vsr_ratio = current_vsr / avg_vsr if avg_vsr > 0 else 1
            
            if vsr_ratio < 0.5:
                self.logger.warning(f"{ticker}: VSR DETERIORATION DETECTED - Current VSR: {current_vsr:.0f} "
                                  f"({vsr_ratio*100:.0f}% of average {avg_vsr:.0f})")
                return {
                    'exit_signal': 'VSR_DETERIORATION',
                    'current_vsr': current_vsr,
                    'avg_vsr': avg_vsr,
                    'vsr_ratio': vsr_ratio,
                    'reason': f"VSR dropped to {vsr_ratio*100:.0f}% of average"
                }
            
            self.logger.debug(f"{ticker}: VSR Check - Current: {current_vsr:.0f}, Avg: {avg_vsr:.0f}, Ratio: {vsr_ratio*100:.0f}%")
            
        except Exception as e:
            self.logger.error(f"Error checking VSR conditions for {ticker}: {e}")
        
        return None

    def check_loss_threshold(self, ticker, current_price):
        """Check if position has -2% loss"""
        if ticker not in self.tracked_positions:
            return None
        
        position_data = self.tracked_positions[ticker]
        entry_price = position_data.get("entry_price", 0)
        
        if entry_price <= 0:
            return None
        
        loss_pct = ((current_price - entry_price) / entry_price) * 100
        
        if loss_pct <= -2.0:
            self.logger.warning(f"{ticker}: LOSS THRESHOLD BREACHED - Current loss: {loss_pct:.2f}%")
            return {
                'exit_signal': 'LOSS_THRESHOLD',
                'loss_pct': loss_pct,
                'entry_price': entry_price,
                'current_price': current_price,
                'reason': f"Position loss exceeded -2% (current: {loss_pct:.2f}%)"
            }
        
        return None
'''
        modified_lines.insert(insert_index, vsr_methods)
    
    # Write the modified file
    with open(original_file, 'w') as f:
        f.writelines(modified_lines)
    
    print("VSR modifications applied successfully!")
    print(f"Backup saved as: {backup_file}")
    print("\nNew features added:")
    print("1. VSR (Volume Spread Ratio) monitoring on hourly timeframe")
    print("2. Exit if hourly VSR drops below 50% of average")
    print("3. Exit if position shows -2% loss")
    print("\nThe watchdog will now monitor both ATR-based stop losses and VSR conditions.")

if __name__ == "__main__":
    apply_vsr_modifications()