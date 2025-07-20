#!/usr/bin/env python
"""
VSR Modifications for SL_watchdog.py
This file contains the code additions needed to implement VSR monitoring
"""

# Add these imports at the top of the file (after existing imports)
import numpy as np

# Add these attributes to __init__ method (after line ~186)
# VSR tracking data
self.vsr_data = {}  # ticker -> {'entry_vsr': value, 'current_vsr': value, 'vsr_history': [], 'last_hourly_check': datetime}
self.hourly_candles = {}  # ticker -> list of hourly candles for VSR calculation
self.last_vsr_check = 0  # Track last VSR check time

# Add these methods to the SLWatchdog class:

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

# Modify the check_atr_stop_loss method by adding these lines after line ~1308:
# (Right after the position verification check)

        # Check VSR conditions (hourly)
        vsr_signal = self.check_vsr_conditions(ticker)
        if vsr_signal:
            # Queue order for VSR-based exit
            self.queue_order(
                ticker,
                expected_quantity,
                "SELL",
                f"VSR_EXIT: {vsr_signal['reason']}",
                current_price
            )
            return
        
        # Check -2% loss threshold
        loss_signal = self.check_loss_threshold(ticker, current_price)
        if loss_signal:
            # Queue order for loss threshold exit
            self.queue_order(
                ticker,
                expected_quantity,
                "SELL",
                f"LOSS_EXIT: {loss_signal['reason']}",
                current_price
            )
            return

# Update the logging message in __init__ (around line 229):
# Replace "ATR-BASED TRAILING STOP LOSS ENABLED" with:
        self.logger.info("ATR-BASED TRAILING STOP LOSS WITH VSR MONITORING ENABLED")
        
# Add these log lines after the ATR logging section (around line 238):
        self.logger.info("")
        self.logger.info("VSR-BASED EXIT RULES (Hourly):")
        self.logger.info("- Exit if hourly VSR drops < 50% of entry VSR")
        self.logger.info("- Exit if position shows -2% loss")
        self.logger.info("")