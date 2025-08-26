#!/usr/bin/env python3
"""
SL_Watch_ICT.py - ICT Concept-based Stop Loss Analysis for CNC Positions
Analyzes portfolio positions using Inner Circle Trader concepts on Hourly and Daily timeframes
Provides optimal stop loss recommendations based on market structure and order flow
"""

import os
import sys
import json
import logging
import datetime
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import required modules
from kiteconnect import KiteConnect
from scanners.VSR_Momentum_Scanner import load_daily_config

class MarketStructure(Enum):
    """Market structure states based on ICT concepts"""
    BULLISH_TRENDING = "Bullish Trending"
    BEARISH_TRENDING = "Bearish Trending"
    BULLISH_PULLBACK = "Bullish Pullback"
    BEARISH_PULLBACK = "Bearish Pullback"
    BULLISH_CORRECTION = "Bullish Correction"
    BEARISH_CORRECTION = "Bearish Correction"
    RANGING = "Ranging/Consolidation"

@dataclass
class ICTLevel:
    """ICT key level data structure"""
    price: float
    level_type: str  # 'FVG', 'OB', 'LIQUIDITY', 'OTE', 'PREMIUM', 'DISCOUNT'
    strength: int  # 1-5 strength rating
    timeframe: str
    timestamp: datetime.datetime

@dataclass
class ICTAnalysis:
    """Complete ICT analysis result"""
    ticker: str
    current_price: float
    position_price: float
    market_structure: MarketStructure
    key_levels: List[ICTLevel]
    optimal_sl: float
    sl_reasoning: str
    trend_strength: float  # 0-100
    pullback_probability: float  # 0-100
    correction_probability: float  # 0-100
    recommendation: str
    timeframe: str

class ICTAnalyzer:
    """ICT concept analyzer for stop loss optimization"""
    
    def __init__(self, user_name: str = 'Sai'):
        """Initialize ICT Analyzer"""
        self.user_name = user_name
        self.setup_logging()
        self.kite = self.initialize_kite()
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                              'logs', 'ict_analysis')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, 
                               f'sl_watch_ict_{datetime.date.today().strftime("%Y%m%d")}.log')
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def initialize_kite(self) -> KiteConnect:
        """Initialize Kite connection"""
        try:
            config = load_daily_config(self.user_name)
            credential_section = f'API_CREDENTIALS_{self.user_name}'
            
            api_key = config.get(credential_section, 'api_key')
            access_token = config.get(credential_section, 'access_token')
            
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            
            # Test connection
            profile = kite.profile()
            self.logger.info(f"Connected to Kite as: {profile.get('user_name', 'Unknown')}")
            
            return kite
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Kite connection: {e}")
            raise
    
    def get_all_positions(self, include_mis: bool = True, include_holdings: bool = True) -> List[Dict]:
        """Fetch all positions from portfolio (CNC, MIS, and Holdings)"""
        try:
            positions = self.kite.positions()
            all_positions = []
            
            # Get active positions
            for position in positions.get('net', []):
                # Include both CNC and MIS positions based on parameter
                if position['quantity'] > 0:
                    if position['product'] == 'CNC' or (include_mis and position['product'] == 'MIS'):
                        all_positions.append({
                            'ticker': position['tradingsymbol'],
                            'quantity': position['quantity'],
                            'average_price': position['average_price'],
                            'last_price': position['last_price'],
                            'pnl': position['pnl'],
                            'pnl_percent': (position['pnl'] / (position['average_price'] * position['quantity'])) * 100,
                            'product_type': position['product']  # Track if CNC or MIS
                        })
            
            # Add holdings (stocks held in demat including T1)
            if include_holdings:
                holdings = self.kite.holdings()
                for holding in holdings:
                    if holding['quantity'] > 0:
                        # Check if not already in positions (avoid duplicates)
                        ticker = holding['tradingsymbol']
                        if not any(p['ticker'] == ticker for p in all_positions):
                            all_positions.append({
                                'ticker': ticker,
                                'quantity': holding['quantity'],
                                'average_price': holding['average_price'],
                                'last_price': holding['last_price'],
                                'pnl': holding['pnl'],
                                'pnl_percent': (holding['pnl'] / (holding['average_price'] * holding['quantity'])) * 100 if holding['quantity'] > 0 else 0,
                                'product_type': 'HOLDING'  # Mark as holding
                            })
            
            cnc_count = sum(1 for p in all_positions if p['product_type'] == 'CNC')
            mis_count = sum(1 for p in all_positions if p['product_type'] == 'MIS')
            holding_count = sum(1 for p in all_positions if p['product_type'] == 'HOLDING')
            self.logger.info(f"Found {cnc_count} CNC, {mis_count} MIS, and {holding_count} HOLDING positions")
            return all_positions
            
        except Exception as e:
            self.logger.error(f"Error fetching positions: {e}")
            return []
    
    def get_cnc_positions(self) -> List[Dict]:
        """Fetch only CNC positions from portfolio (backward compatibility)"""
        return [p for p in self.get_all_positions(include_mis=False) if p['product_type'] == 'CNC']
    
    def fetch_historical_data(self, ticker: str, interval: str, days: int = 60) -> pd.DataFrame:
        """Fetch historical data for analysis"""
        try:
            # Get instrument token
            instruments = self.kite.ltp([f'NSE:{ticker}'])
            if f'NSE:{ticker}' not in instruments:
                self.logger.error(f"Could not find instrument token for {ticker}")
                return pd.DataFrame()
            
            instrument_token = list(instruments[f'NSE:{ticker}'].values())[0]
            
            # Calculate date range
            to_date = datetime.datetime.now()
            from_date = to_date - datetime.timedelta(days=days)
            
            # Fetch historical data
            historical_data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date.strftime('%Y-%m-%d'),
                to_date=to_date.strftime('%Y-%m-%d'),
                interval=interval
            )
            
            if not historical_data:
                return pd.DataFrame()
            
            df = pd.DataFrame(historical_data)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching data for {ticker}: {e}")
            return pd.DataFrame()
    
    def identify_market_structure(self, df: pd.DataFrame) -> Tuple[MarketStructure, float]:
        """Identify market structure using ICT concepts"""
        if df.empty or len(df) < 20:
            return MarketStructure.RANGING, 0.0
        
        # Identify swing highs and lows
        highs = []
        lows = []
        
        for i in range(2, len(df) - 2):
            # Swing high
            if (df['high'].iloc[i] > df['high'].iloc[i-1] and 
                df['high'].iloc[i] > df['high'].iloc[i-2] and
                df['high'].iloc[i] > df['high'].iloc[i+1] and 
                df['high'].iloc[i] > df['high'].iloc[i+2]):
                highs.append((i, df['high'].iloc[i]))
            
            # Swing low
            if (df['low'].iloc[i] < df['low'].iloc[i-1] and 
                df['low'].iloc[i] < df['low'].iloc[i-2] and
                df['low'].iloc[i] < df['low'].iloc[i+1] and 
                df['low'].iloc[i] < df['low'].iloc[i+2]):
                lows.append((i, df['low'].iloc[i]))
        
        if len(highs) < 2 or len(lows) < 2:
            return MarketStructure.RANGING, 0.0
        
        # Analyze structure
        last_high = highs[-1][1]
        prev_high = highs[-2][1]
        last_low = lows[-1][1]
        prev_low = lows[-2][1]
        
        current_price = df['close'].iloc[-1]
        
        # Calculate trend strength
        price_range = df['high'].max() - df['low'].min()
        trend_move = abs(df['close'].iloc[-1] - df['close'].iloc[0])
        trend_strength = min((trend_move / price_range) * 100, 100) if price_range > 0 else 0
        
        # Determine structure
        if last_high > prev_high and last_low > prev_low:
            # Bullish structure
            if current_price > last_high * 0.98:
                return MarketStructure.BULLISH_TRENDING, trend_strength
            elif current_price > last_low:
                # Check if pullback or correction
                retracement = (last_high - current_price) / (last_high - last_low) if last_high > last_low else 0
                if retracement < 0.618:
                    return MarketStructure.BULLISH_PULLBACK, trend_strength
                else:
                    return MarketStructure.BULLISH_CORRECTION, trend_strength
            else:
                return MarketStructure.BULLISH_CORRECTION, trend_strength
                
        elif last_high < prev_high and last_low < prev_low:
            # Bearish structure
            if current_price < last_low * 1.02:
                return MarketStructure.BEARISH_TRENDING, trend_strength
            elif current_price < last_high:
                # Check if pullback or correction
                retracement = (current_price - last_low) / (last_high - last_low) if last_high > last_low else 0
                if retracement < 0.618:
                    return MarketStructure.BEARISH_PULLBACK, trend_strength
                else:
                    return MarketStructure.BEARISH_CORRECTION, trend_strength
            else:
                return MarketStructure.BEARISH_CORRECTION, trend_strength
        else:
            return MarketStructure.RANGING, trend_strength
    
    def find_order_blocks(self, df: pd.DataFrame, lookback: int = 50) -> List[ICTLevel]:
        """Identify order blocks (OB) in the price action"""
        order_blocks = []
        
        if len(df) < lookback:
            return order_blocks
        
        recent_df = df.tail(lookback)
        
        for i in range(1, len(recent_df) - 1):
            # Bullish order block (last down candle before up move)
            if (recent_df['close'].iloc[i] < recent_df['open'].iloc[i] and  # Down candle
                recent_df['close'].iloc[i+1] > recent_df['open'].iloc[i+1] and  # Followed by up candle
                recent_df['high'].iloc[i+1] > recent_df['high'].iloc[i]):  # Breaking structure
                
                ob_level = ICTLevel(
                    price=(recent_df['high'].iloc[i] + recent_df['low'].iloc[i]) / 2,
                    level_type='OB_BULLISH',
                    strength=3,
                    timeframe='60minute' if '60' in str(df.index.freq) else 'day',
                    timestamp=recent_df.index[i]
                )
                order_blocks.append(ob_level)
            
            # Bearish order block (last up candle before down move)
            if (recent_df['close'].iloc[i] > recent_df['open'].iloc[i] and  # Up candle
                recent_df['close'].iloc[i+1] < recent_df['open'].iloc[i+1] and  # Followed by down candle
                recent_df['low'].iloc[i+1] < recent_df['low'].iloc[i]):  # Breaking structure
                
                ob_level = ICTLevel(
                    price=(recent_df['high'].iloc[i] + recent_df['low'].iloc[i]) / 2,
                    level_type='OB_BEARISH',
                    strength=3,
                    timeframe='60minute' if '60' in str(df.index.freq) else 'day',
                    timestamp=recent_df.index[i]
                )
                order_blocks.append(ob_level)
        
        return order_blocks
    
    def find_fair_value_gaps(self, df: pd.DataFrame, min_gap_percent: float = 0.5) -> List[ICTLevel]:
        """Identify Fair Value Gaps (FVG) in the price action"""
        fvgs = []
        
        if len(df) < 3:
            return fvgs
        
        for i in range(1, len(df) - 1):
            # Bullish FVG
            if df['low'].iloc[i+1] > df['high'].iloc[i-1]:
                gap_size = df['low'].iloc[i+1] - df['high'].iloc[i-1]
                gap_percent = (gap_size / df['close'].iloc[i]) * 100
                
                if gap_percent >= min_gap_percent:
                    fvg_level = ICTLevel(
                        price=(df['low'].iloc[i+1] + df['high'].iloc[i-1]) / 2,
                        level_type='FVG_BULLISH',
                        strength=min(5, int(gap_percent)),
                        timeframe='60minute' if '60' in str(df.index.freq) else 'day',
                        timestamp=df.index[i]
                    )
                    fvgs.append(fvg_level)
            
            # Bearish FVG
            if df['high'].iloc[i+1] < df['low'].iloc[i-1]:
                gap_size = df['low'].iloc[i-1] - df['high'].iloc[i+1]
                gap_percent = (gap_size / df['close'].iloc[i]) * 100
                
                if gap_percent >= min_gap_percent:
                    fvg_level = ICTLevel(
                        price=(df['high'].iloc[i+1] + df['low'].iloc[i-1]) / 2,
                        level_type='FVG_BEARISH',
                        strength=min(5, int(gap_percent)),
                        timeframe='60minute' if '60' in str(df.index.freq) else 'day',
                        timestamp=df.index[i]
                    )
                    fvgs.append(fvg_level)
        
        return fvgs
    
    def find_liquidity_levels(self, df: pd.DataFrame) -> List[ICTLevel]:
        """Identify key liquidity levels (equal highs/lows)"""
        liquidity_levels = []
        
        if len(df) < 20:
            return liquidity_levels
        
        # Find recent highs and lows
        recent_high = df['high'].tail(20).max()
        recent_low = df['low'].tail(20).min()
        
        # Count touches at these levels
        high_touches = sum(abs(df['high'] - recent_high) / recent_high < 0.002)
        low_touches = sum(abs(df['low'] - recent_low) / recent_low < 0.002)
        
        if high_touches >= 2:
            liquidity_levels.append(ICTLevel(
                price=recent_high,
                level_type='LIQUIDITY_HIGH',
                strength=min(5, high_touches),
                timeframe='60minute' if '60' in str(df.index.freq) else 'day',
                timestamp=df.index[-1]
            ))
        
        if low_touches >= 2:
            liquidity_levels.append(ICTLevel(
                price=recent_low,
                level_type='LIQUIDITY_LOW',
                strength=min(5, low_touches),
                timeframe='60minute' if '60' in str(df.index.freq) else 'day',
                timestamp=df.index[-1]
            ))
        
        return liquidity_levels
    
    def calculate_ote_levels(self, df: pd.DataFrame) -> List[ICTLevel]:
        """Calculate Optimal Trade Entry (OTE) levels using Fibonacci"""
        ote_levels = []
        
        if len(df) < 10:
            return ote_levels
        
        # Find recent swing high and low
        recent_high = df['high'].tail(20).max()
        recent_low = df['low'].tail(20).min()
        range_size = recent_high - recent_low
        
        if range_size <= 0:
            return ote_levels
        
        current_price = df['close'].iloc[-1]
        
        # Calculate Fibonacci levels
        fib_618 = recent_low + (range_size * 0.618)
        fib_705 = recent_low + (range_size * 0.705)
        fib_79 = recent_low + (range_size * 0.79)
        
        # Determine if we're in discount or premium
        if current_price < recent_low + (range_size * 0.5):
            # In discount zone
            ote_levels.append(ICTLevel(
                price=fib_618,
                level_type='OTE_DISCOUNT',
                strength=4,
                timeframe='60minute' if '60' in str(df.index.freq) else 'day',
                timestamp=df.index[-1]
            ))
        else:
            # In premium zone
            ote_levels.append(ICTLevel(
                price=fib_705,
                level_type='OTE_PREMIUM',
                strength=4,
                timeframe='60minute' if '60' in str(df.index.freq) else 'day',
                timestamp=df.index[-1]
            ))
        
        return ote_levels
    
    def calculate_optimal_stop_loss(self, 
                                   current_price: float,
                                   position_price: float,
                                   market_structure: MarketStructure,
                                   key_levels: List[ICTLevel]) -> Tuple[float, str]:
        """Calculate optimal stop loss based on ICT concepts"""
        
        # Sort levels by price
        support_levels = [level for level in key_levels 
                         if level.price < current_price and 
                         level.level_type in ['OB_BULLISH', 'FVG_BULLISH', 'LIQUIDITY_LOW', 'OTE_DISCOUNT']]
        support_levels.sort(key=lambda x: x.price, reverse=True)
        
        resistance_levels = [level for level in key_levels 
                            if level.price > current_price and 
                            level.level_type in ['OB_BEARISH', 'FVG_BEARISH', 'LIQUIDITY_HIGH', 'OTE_PREMIUM']]
        resistance_levels.sort(key=lambda x: x.price)
        
        # Default stop loss (5% from position)
        default_sl = position_price * 0.95
        optimal_sl = default_sl
        reasoning = "Default 5% stop loss"
        
        # Adjust based on market structure
        if market_structure == MarketStructure.BULLISH_TRENDING:
            # Use nearest strong support
            if support_levels:
                strongest_support = max(support_levels, key=lambda x: x.strength)
                optimal_sl = strongest_support.price * 0.99  # Just below support
                reasoning = f"Below {strongest_support.level_type} support at {strongest_support.price:.2f}"
            
        elif market_structure == MarketStructure.BULLISH_PULLBACK:
            # Tighter stop at recent swing low
            if support_levels and len(support_levels) >= 2:
                optimal_sl = support_levels[1].price * 0.99  # Second support level
                reasoning = f"Below pullback support at {support_levels[1].price:.2f}"
            
        elif market_structure == MarketStructure.BULLISH_CORRECTION:
            # Wider stop for correction
            if support_levels:
                # Use furthest strong support
                optimal_sl = min([level.price for level in support_levels]) * 0.98
                reasoning = "Wide stop for correction phase"
            
        elif market_structure in [MarketStructure.BEARISH_TRENDING, 
                                 MarketStructure.BEARISH_PULLBACK,
                                 MarketStructure.BEARISH_CORRECTION]:
            # For bearish structures, use recent high as stop
            if resistance_levels:
                optimal_sl = resistance_levels[0].price * 1.01
                reasoning = f"Above {resistance_levels[0].level_type} resistance"
            else:
                optimal_sl = current_price * 0.92  # Tighter stop for bearish
                reasoning = "Tight stop for bearish structure"
        
        else:  # RANGING
            # Use range boundaries
            if support_levels and resistance_levels:
                range_bottom = min([level.price for level in support_levels])
                optimal_sl = range_bottom * 0.99
                reasoning = f"Below range support at {range_bottom:.2f}"
        
        # Ensure stop loss is not too far from current price (max 10%)
        max_sl_distance = current_price * 0.10
        if current_price - optimal_sl > max_sl_distance:
            optimal_sl = current_price - max_sl_distance
            reasoning += " (capped at 10% from current)"
        
        # Ensure stop loss is below position price for long positions
        if optimal_sl >= position_price:
            optimal_sl = position_price * 0.98
            reasoning = "Below entry price"
        
        return optimal_sl, reasoning
    
    def analyze_position(self, position: Dict, timeframe: str) -> ICTAnalysis:
        """Perform complete ICT analysis on a position"""
        ticker = position['ticker']
        self.logger.info(f"Analyzing {ticker} on {timeframe} timeframe")
        
        # Fetch historical data
        interval = '60minute' if timeframe == 'hourly' else 'day'
        df = self.fetch_historical_data(ticker, interval)
        
        if df.empty:
            self.logger.error(f"No data available for {ticker}")
            return None
        
        # Identify market structure
        market_structure, trend_strength = self.identify_market_structure(df)
        
        # Find key levels
        order_blocks = self.find_order_blocks(df)
        fvgs = self.find_fair_value_gaps(df)
        liquidity_levels = self.find_liquidity_levels(df)
        ote_levels = self.calculate_ote_levels(df)
        
        # Combine all key levels
        key_levels = order_blocks + fvgs + liquidity_levels + ote_levels
        
        # Calculate probabilities
        pullback_probability = 0.0
        correction_probability = 0.0
        
        if 'PULLBACK' in market_structure.value:
            pullback_probability = 70.0
            correction_probability = 30.0
        elif 'CORRECTION' in market_structure.value:
            pullback_probability = 30.0
            correction_probability = 70.0
        elif 'TRENDING' in market_structure.value:
            pullback_probability = 50.0
            correction_probability = 20.0
        else:  # RANGING
            pullback_probability = 40.0
            correction_probability = 40.0
        
        # Calculate optimal stop loss
        current_price = df['close'].iloc[-1]
        optimal_sl, sl_reasoning = self.calculate_optimal_stop_loss(
            current_price,
            position['average_price'],
            market_structure,
            key_levels
        )
        
        # Generate recommendation
        if market_structure in [MarketStructure.BULLISH_TRENDING, MarketStructure.BULLISH_PULLBACK]:
            recommendation = "HOLD - Bullish structure intact"
        elif market_structure == MarketStructure.BULLISH_CORRECTION:
            recommendation = "MONITOR CLOSELY - In correction phase"
        elif market_structure in [MarketStructure.BEARISH_TRENDING, MarketStructure.BEARISH_CORRECTION]:
            recommendation = "CONSIDER EXIT - Bearish structure"
        else:
            recommendation = "HOLD WITH CAUTION - Ranging market"
        
        return ICTAnalysis(
            ticker=ticker,
            current_price=current_price,
            position_price=position['average_price'],
            market_structure=market_structure,
            key_levels=key_levels,
            optimal_sl=optimal_sl,
            sl_reasoning=sl_reasoning,
            trend_strength=trend_strength,
            pullback_probability=pullback_probability,
            correction_probability=correction_probability,
            recommendation=recommendation,
            timeframe=timeframe
        )
    
    def format_analysis_report(self, analysis: ICTAnalysis) -> str:
        """Format ICT analysis into readable report"""
        report = f"""
{'='*80}
ICT ANALYSIS REPORT - {analysis.ticker} ({analysis.timeframe.upper()})
{'='*80}

POSITION DETAILS:
  Entry Price: ₹{analysis.position_price:.2f}
  Current Price: ₹{analysis.current_price:.2f}
  P&L: ₹{analysis.current_price - analysis.position_price:.2f} ({((analysis.current_price - analysis.position_price) / analysis.position_price * 100):.2f}%)

MARKET STRUCTURE:
  Structure: {analysis.market_structure.value}
  Trend Strength: {analysis.trend_strength:.1f}%
  Pullback Probability: {analysis.pullback_probability:.1f}%
  Correction Probability: {analysis.correction_probability:.1f}%

KEY ICT LEVELS:
"""
        # Add key levels
        for level in sorted(analysis.key_levels, key=lambda x: abs(x.price - analysis.current_price)):
            distance = ((level.price - analysis.current_price) / analysis.current_price) * 100
            report += f"  {level.level_type}: ₹{level.price:.2f} (Strength: {level.strength}/5) [{distance:+.2f}% away]\n"
        
        report += f"""
STOP LOSS RECOMMENDATION:
  Optimal SL: ₹{analysis.optimal_sl:.2f}
  SL Distance: {((analysis.current_price - analysis.optimal_sl) / analysis.current_price * 100):.2f}%
  Reasoning: {analysis.sl_reasoning}

ACTION RECOMMENDATION:
  {analysis.recommendation}

{'='*80}
"""
        return report
    
    def save_analysis_to_json(self, analyses: List[ICTAnalysis]):
        """Save analysis results to JSON file"""
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                 'portfolio', 'ict_analysis')
        os.makedirs(output_dir, exist_ok=True)
        
        output_file = os.path.join(output_dir, 
                                  f'ict_sl_analysis_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        
        results = []
        for analysis in analyses:
            if analysis:
                results.append({
                    'ticker': analysis.ticker,
                    'timeframe': analysis.timeframe,
                    'current_price': float(analysis.current_price),
                    'position_price': float(analysis.position_price),
                    'market_structure': analysis.market_structure.value,
                    'optimal_sl': float(analysis.optimal_sl),
                    'sl_reasoning': analysis.sl_reasoning,
                    'trend_strength': float(analysis.trend_strength),
                    'pullback_probability': float(analysis.pullback_probability),
                    'correction_probability': float(analysis.correction_probability),
                    'recommendation': analysis.recommendation,
                    'product_type': getattr(analysis, 'product_type', 'CNC'),  # Track product type
                    'analysis_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        self.logger.info(f"Analysis saved to {output_file}")
    
    def run(self, include_mis: bool = True):
        """Main execution method"""
        self.logger.info("="*80)
        self.logger.info("Starting ICT-based Stop Loss Analysis")
        self.logger.info("="*80)
        
        # Get all positions (CNC + MIS)
        positions = self.get_all_positions(include_mis=include_mis)
        
        if not positions:
            self.logger.info("No positions found in portfolio")
            return
        
        all_analyses = []
        
        # Analyze each position on both timeframes
        for position in positions:
            self.logger.info(f"\nAnalyzing {position['ticker']}...")
            
            # Hourly timeframe analysis
            hourly_analysis = self.analyze_position(position, 'hourly')
            if hourly_analysis:
                report = self.format_analysis_report(hourly_analysis)
                self.logger.info(report)
                all_analyses.append(hourly_analysis)
            
            # Daily timeframe analysis
            daily_analysis = self.analyze_position(position, 'daily')
            if daily_analysis:
                report = self.format_analysis_report(daily_analysis)
                self.logger.info(report)
                all_analyses.append(daily_analysis)
        
        # Save all analyses to JSON
        if all_analyses:
            self.save_analysis_to_json(all_analyses)
        
        # Summary
        self.logger.info("\n" + "="*80)
        self.logger.info("ANALYSIS SUMMARY")
        self.logger.info("="*80)
        
        for position in positions:
            ticker = position['ticker']
            hourly = next((a for a in all_analyses if a.ticker == ticker and a.timeframe == 'hourly'), None)
            daily = next((a for a in all_analyses if a.ticker == ticker and a.timeframe == 'daily'), None)
            
            if hourly and daily:
                self.logger.info(f"\n{ticker}:")
                self.logger.info(f"  Hourly: {hourly.market_structure.value} | SL: ₹{hourly.optimal_sl:.2f}")
                self.logger.info(f"  Daily:  {daily.market_structure.value} | SL: ₹{daily.optimal_sl:.2f}")
                self.logger.info(f"  Final SL: ₹{min(hourly.optimal_sl, daily.optimal_sl):.2f} (most conservative)")
        
        self.logger.info("\n" + "="*80)
        self.logger.info("ICT Analysis Complete")
        self.logger.info("="*80)


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ICT-based Stop Loss Analysis for CNC Positions')
    parser.add_argument('--user', '-u', type=str, default='Sai', 
                       help='User name for Kite connection')
    parser.add_argument('--ticker', '-t', type=str, 
                       help='Analyze specific ticker only')
    
    args = parser.parse_args()
    
    try:
        analyzer = ICTAnalyzer(user_name=args.user)
        analyzer.run()
    except Exception as e:
        logging.error(f"Error running ICT analysis: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()