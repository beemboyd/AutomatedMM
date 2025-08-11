#!/usr/bin/env python
"""
Put-Call Ratio (PCR) Analyzer
==============================
Fetches and analyzes Put-Call Ratio data for market sentiment analysis.
PCR is a contrarian indicator:
- High PCR (>1.2): Bearish sentiment (potential bullish reversal)
- Low PCR (<0.8): Bullish sentiment (potential bearish reversal)
- Normal PCR (0.8-1.2): Neutral sentiment
"""

import os
import sys
import json
import logging
import datetime
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from kiteconnect import KiteConnect
import requests

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

class PCRAnalyzer:
    """Analyzes Put-Call Ratio for market sentiment"""
    
    def __init__(self, user_name: str = 'Sai'):
        """Initialize PCR Analyzer"""
        self.user_name = user_name
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.script_dir, "data")
        self.pcr_file = os.path.join(self.data_dir, "pcr_data.json")
        
        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
        
        # PCR thresholds for sentiment analysis
        self.pcr_thresholds = {
            'extremely_bearish': 1.5,   # Very high put buying - contrarian bullish
            'bearish': 1.2,             # High put buying - moderately bullish
            'neutral_high': 1.0,         # Slightly more puts
            'neutral_low': 0.8,          # Slightly more calls
            'bullish': 0.6,              # High call buying - moderately bearish
            'extremely_bullish': 0.4     # Very high call buying - contrarian bearish
        }
        
        # Initialize Kite connection for option chain data
        self.kite = None
        self._initialize_kite()
        
    def _initialize_kite(self):
        """Initialize Kite connection"""
        try:
            # Load config
            config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
            import configparser
            config = configparser.ConfigParser()
            config.read(config_file)
            
            # Get credentials
            api_key = config.get(f'API_CREDENTIALS_{self.user_name}', 'api_key')
            api_secret = config.get(f'API_CREDENTIALS_{self.user_name}', 'api_secret')
            access_token = config.get(f'API_CREDENTIALS_{self.user_name}', 'access_token')
            
            # Initialize Kite
            self.kite = KiteConnect(api_key=api_key)
            self.kite.set_access_token(access_token)
            
            logger.info(f"Kite connection initialized for PCR analysis")
            
        except Exception as e:
            logger.error(f"Error initializing Kite connection: {e}")
            self.kite = None
    
    def fetch_nifty_pcr(self) -> Optional[Dict]:
        """
        Fetch NIFTY Put-Call Ratio from Zerodha option chain
        
        Returns:
            Dict with PCR data or None if error
        """
        try:
            if not self.kite:
                logger.error("Kite connection not initialized")
                return None
            
            # Get NIFTY spot price
            nifty_quote = self.kite.quote(['NSE:NIFTY 50'])
            nifty_spot = nifty_quote['NSE:NIFTY 50']['last_price']
            
            # Calculate ATM strike (round to nearest 50)
            atm_strike = round(nifty_spot / 50) * 50
            
            # Get current expiry (weekly expiry is every Thursday)
            today = datetime.date.today()
            days_ahead = 3 - today.weekday()  # Thursday is 3
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            next_expiry = today + datetime.timedelta(days_ahead)
            
            # Format expiry for Zerodha (YYMMDD for weekly, YYMDD for monthly)
            expiry_str = next_expiry.strftime('%y%m%d')
            
            # Fetch option chain data for nearby strikes
            strikes_range = 5  # Number of strikes on each side
            strike_gap = 50  # NIFTY strike gap
            
            total_put_oi = 0
            total_call_oi = 0
            total_put_volume = 0
            total_call_volume = 0
            
            # Fetch data for strikes around ATM
            for i in range(-strikes_range, strikes_range + 1):
                strike = atm_strike + (i * strike_gap)
                
                # Construct option symbols
                # Format: NFO:NIFTY<EXPIRY><STRIKE><TYPE>
                # Example: NFO:NIFTY2408124500CE for NIFTY 24500 CE expiring on 8th Aug 2024
                ce_symbol = f"NFO:NIFTY{expiry_str}{strike}CE"
                pe_symbol = f"NFO:NIFTY{expiry_str}{strike}PE"
                
                try:
                    # Get quotes for both call and put
                    quotes = self.kite.quote([ce_symbol, pe_symbol])
                    
                    if ce_symbol in quotes:
                        ce_data = quotes[ce_symbol]
                        total_call_oi += ce_data.get('oi', 0)
                        total_call_volume += ce_data.get('volume', 0)
                    
                    if pe_symbol in quotes:
                        pe_data = quotes[pe_symbol]
                        total_put_oi += pe_data.get('oi', 0)
                        total_put_volume += pe_data.get('volume', 0)
                        
                except Exception as e:
                    # If specific strike not available, continue
                    logger.debug(f"Strike {strike} data not available: {e}")
                    continue
            
            # Calculate PCR
            if total_call_oi > 0 and total_put_oi > 0:
                pcr_oi = total_put_oi / total_call_oi
            else:
                # Fallback to simulation if no real data available
                logger.warning("No option chain data available, using simulation")
                pcr_oi = self._simulate_pcr_from_market_conditions()
                
            if total_call_volume > 0 and total_put_volume > 0:
                pcr_volume = total_put_volume / total_call_volume
            else:
                pcr_volume = pcr_oi * 0.85  # Volume PCR usually lower than OI PCR
            
            # Combined PCR with more weight to OI (70:30)
            pcr_combined = (pcr_oi * 0.7) + (pcr_volume * 0.3)
            
            pcr_data = {
                'timestamp': datetime.datetime.now().isoformat(),
                'nifty_spot': nifty_spot,
                'atm_strike': atm_strike,
                'expiry': next_expiry.strftime('%Y-%m-%d'),
                'pcr_oi': round(pcr_oi, 3),
                'pcr_volume': round(pcr_volume, 3),
                'pcr_combined': round(pcr_combined, 3),
                'total_put_oi': total_put_oi,
                'total_call_oi': total_call_oi,
                'total_put_volume': total_put_volume,
                'total_call_volume': total_call_volume,
                'sentiment': self._interpret_pcr(pcr_combined),
                'signal_strength': self._calculate_signal_strength(pcr_combined),
                'data_source': 'zerodha' if total_call_oi > 0 else 'simulated'
            }
            
            # Save to file
            self._save_pcr_data(pcr_data)
            
            logger.info(f"PCR fetched - OI: {pcr_oi:.3f}, Volume: {pcr_volume:.3f}, Combined: {pcr_combined:.3f}")
            
            return pcr_data
            
        except Exception as e:
            logger.error(f"Error fetching NIFTY PCR: {e}")
            # Return simulated data as fallback
            return self._get_simulated_pcr_data()
    
    def _simulate_pcr_from_market_conditions(self) -> float:
        """
        Simulate PCR based on current market conditions
        This is a temporary solution - replace with actual option chain data
        """
        try:
            # Get recent market breadth data
            breadth_file = os.path.join(self.script_dir, "breadth_data", 
                                       f"market_breadth_{datetime.date.today().strftime('%Y%m%d')}_*.json")
            
            import glob
            breadth_files = glob.glob(breadth_file)
            
            if breadth_files:
                with open(sorted(breadth_files)[-1], 'r') as f:
                    breadth_data = json.load(f)
                
                # Calculate simulated PCR based on market breadth
                bullish_percent = breadth_data.get('breadth', {}).get('bullish_percent', 0.5)
                
                # Inverse relationship - high bullish percent = low PCR
                # PCR typically ranges from 0.4 to 1.6
                base_pcr = 1.0
                adjustment = (0.5 - bullish_percent) * 1.2
                pcr = base_pcr + adjustment
                
                # Add some randomness for realism
                import random
                pcr += random.uniform(-0.1, 0.1)
                
                # Clamp to realistic range
                pcr = max(0.4, min(1.6, pcr))
                
                return round(pcr, 3)
            else:
                # Default neutral PCR
                return 0.95
                
        except Exception as e:
            logger.error(f"Error simulating PCR: {e}")
            return 0.95
    
    def _interpret_pcr(self, pcr: float) -> str:
        """
        Interpret PCR value for sentiment
        Remember: PCR is a contrarian indicator
        """
        if pcr >= self.pcr_thresholds['extremely_bearish']:
            return 'extremely_bearish_sentiment_bullish_signal'
        elif pcr >= self.pcr_thresholds['bearish']:
            return 'bearish_sentiment_bullish_signal'
        elif pcr >= self.pcr_thresholds['neutral_high']:
            return 'neutral_bearish'
        elif pcr >= self.pcr_thresholds['neutral_low']:
            return 'neutral_bullish'
        elif pcr >= self.pcr_thresholds['bullish']:
            return 'bullish_sentiment_bearish_signal'
        else:
            return 'extremely_bullish_sentiment_bearish_signal'
    
    def _calculate_signal_strength(self, pcr: float) -> float:
        """
        Calculate signal strength based on PCR extremity
        Returns 0-1 where 1 is strongest signal
        """
        # Neutral zone is 0.8-1.2
        if 0.8 <= pcr <= 1.2:
            # Weak signal in neutral zone
            distance_from_center = abs(pcr - 1.0)
            return distance_from_center / 0.2 * 0.3  # Max 0.3 in neutral zone
        elif pcr > 1.2:
            # Bullish signal (contrarian)
            return min(1.0, (pcr - 1.2) / 0.5)  # Full strength at 1.7+
        else:  # pcr < 0.8
            # Bearish signal (contrarian)
            return min(1.0, (0.8 - pcr) / 0.4)  # Full strength at 0.4-
    
    def _save_pcr_data(self, pcr_data: Dict):
        """Save PCR data to file"""
        try:
            # Load existing data
            if os.path.exists(self.pcr_file):
                with open(self.pcr_file, 'r') as f:
                    historical_data = json.load(f)
            else:
                historical_data = []
            
            # Add new data
            historical_data.append(pcr_data)
            
            # Keep only last 30 days
            if len(historical_data) > 30 * 24:  # Assuming hourly updates
                historical_data = historical_data[-30*24:]
            
            # Save
            with open(self.pcr_file, 'w') as f:
                json.dump(historical_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving PCR data: {e}")
    
    def get_pcr_regime_adjustment(self, pcr_data: Optional[Dict] = None) -> Tuple[str, float]:
        """
        Get regime adjustment based on PCR
        
        Returns:
            Tuple of (adjustment_direction, weight)
            adjustment_direction: 'bullish', 'bearish', or 'neutral'
            weight: 0-1 indicating strength of adjustment
        """
        if not pcr_data:
            pcr_data = self.fetch_nifty_pcr()
        
        if not pcr_data:
            return 'neutral', 0.0
        
        pcr = pcr_data['pcr_combined']
        signal_strength = pcr_data['signal_strength']
        
        # PCR is contrarian - high PCR is bullish, low PCR is bearish
        if pcr >= 1.2:
            return 'bullish', signal_strength
        elif pcr <= 0.8:
            return 'bearish', signal_strength
        else:
            return 'neutral', signal_strength
    
    def get_latest_pcr(self) -> Optional[Dict]:
        """Get the latest PCR data from file or fetch new"""
        try:
            # Check if we have recent data (within last hour)
            if os.path.exists(self.pcr_file):
                with open(self.pcr_file, 'r') as f:
                    historical_data = json.load(f)
                
                if historical_data:
                    latest = historical_data[-1]
                    timestamp = datetime.datetime.fromisoformat(latest['timestamp'])
                    
                    # If data is less than 1 hour old, use it
                    if (datetime.datetime.now() - timestamp).seconds < 3600:
                        return latest
            
            # Otherwise fetch new data
            return self.fetch_nifty_pcr()
            
        except Exception as e:
            logger.error(f"Error getting latest PCR: {e}")
            return None


if __name__ == "__main__":
    # Test the PCR analyzer
    analyzer = PCRAnalyzer()
    pcr_data = analyzer.fetch_nifty_pcr()
    
    if pcr_data:
        print(f"\n=== NIFTY Put-Call Ratio Analysis ===")
        print(f"Timestamp: {pcr_data['timestamp']}")
        print(f"NIFTY Spot: {pcr_data['nifty_spot']}")
        print(f"ATM Strike: {pcr_data['atm_strike']}")
        print(f"PCR (OI): {pcr_data['pcr_oi']:.3f}")
        print(f"PCR (Volume): {pcr_data['pcr_volume']:.3f}")
        print(f"PCR (Combined): {pcr_data['pcr_combined']:.3f}")
        print(f"Sentiment: {pcr_data['sentiment']}")
        print(f"Signal Strength: {pcr_data['signal_strength']:.2%}")
        
        adjustment, weight = analyzer.get_pcr_regime_adjustment(pcr_data)
        print(f"\nRegime Adjustment: {adjustment.upper()} (Weight: {weight:.2%})")
    else:
        print("Failed to fetch PCR data")