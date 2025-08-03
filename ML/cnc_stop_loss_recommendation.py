#!/usr/bin/env python3
"""
CNC Stop Loss Recommendation Script

This script reads existing CNC positions from Zerodha, calculates dynamic
stop loss values based on ATR and market regime, and provides recommendations
with detailed reasoning.

Key features:
- Uses SMALLCAP, MIDCAP, and TOP100CASE indices as market regime benchmarks
- Categorizes stocks as small cap, mid cap, or large cap
- References appropriate index for each stock's market regime detection
- Provides adaptive stop loss values based on stock's behavior relative to index
- Generates detailed stop loss recommendations with explanations
"""

import os
import sys
import json
import logging
import argparse
import pandas as pd
from datetime import datetime
from tabulate import tabulate
import webbrowser
import matplotlib.pyplot as plt
from io import BytesIO
import base64

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ML.models.dynamic_stop_loss import DynamicStopLossModel, PositionType
from ML.utils.atr_calculator import ATRCalculator
from ML.utils.market_regime import MarketRegimeDetector, MarketRegimeType
from data_handler import get_data_handler
from state_manager import get_state_manager
from config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CNCStopLossRecommender:
    """
    Generates stop loss recommendations for CNC positions in Zerodha account.
    Analyzes market regime and volatility to provide dynamic stop loss values,
    using SMALLCAP, MIDCAP, and TOP100CASE indices as market benchmarks.
    """

    def __init__(self, cnc_file_path=None, output_file=None):
        """
        Initialize the recommender.

        Args:
            cnc_file_path (str): Path to CNC positions JSON file. If None, will use data from state manager.
            output_file (str): Path to output recommendations file. If None, will use default path.
        """
        self.config = get_config()
        self.data_handler = get_data_handler()
        self.state_manager = get_state_manager()

        # Initialize models
        self.stop_loss_model = DynamicStopLossModel()
        self.atr_calculator = ATRCalculator(period=14)
        self.regime_detector = MarketRegimeDetector()

        # Define reference indices (using Zerodha ticker formats)
        self.small_cap_index = "SMALLCAP"
        self.mid_cap_index = "MIDCAP"
        self.large_cap_index = "TOP100CASE"

        # Stock categorization by market cap
        # Small cap stocks generally have market cap < $2 billion
        self.small_cap_stocks = ["ACI", "CCL", "RRKABEL", "ELECON"]

        # Mid cap stocks generally have market cap between $2-10 billion
        self.mid_cap_stocks = ["COFORGE", "CREDITACC", "SCHAEFFLER", "TIMKEN"]

        # Large cap stocks generally have market cap > $10 billion
        self.large_cap_stocks = ["RELIANCE"]

        # Cache for index regime data
        self.index_data_cache = {}

        # File paths
        self.cnc_file_path = cnc_file_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'cnc_positions.json'
        )

        # Default output file location
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = output_file or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'ML', 'results', f'sl_recommendations_{timestamp}.xlsx'
        )

        # Ensure results directory exists
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)

        # ATR settings
        self.atr_timeframe = self.config.get('Trading', 'risk_atr_timeframe', fallback="day")
        self.lookback_days = self.config.get_int('ML', 'lookback_days', fallback=30)

        # Minimum price distance for stop loss
        self.min_price_distance_pct = self.config.get_float('ML', 'min_stop_loss_distance_pct', fallback=0.5)

        logger.info("Initialized CNCStopLossRecommender with SMALLCAP, MIDCAP, and TOP100CASE indices")
    
    def load_cnc_positions(self):
        """
        Load CNC positions from JSON file or state manager.
        
        Returns:
            dict: Dictionary of CNC positions
        """
        try:
            # First try to read from file
            if os.path.exists(self.cnc_file_path):
                with open(self.cnc_file_path, 'r') as f:
                    data = json.load(f)
                positions = data.get('positions', {})
                
                # Filter for CNC positions only
                cnc_positions = {
                    ticker: pos for ticker, pos in positions.items()
                    if pos.get('product_type') == 'CNC'
                }
                
                logger.info(f"Loaded {len(cnc_positions)} CNC positions from file")
                return cnc_positions
            
            # If file doesn't exist, try state manager
            logger.info("CNC positions file not found, trying state manager")
            all_positions = self.state_manager.get_all_positions()
            
            # Filter for CNC positions
            cnc_positions = {
                ticker: pos for ticker, pos in all_positions.items()
                if pos.get('product_type') == 'CNC'
            }
            
            logger.info(f"Loaded {len(cnc_positions)} CNC positions from state manager")
            return cnc_positions
        
        except Exception as e:
            logger.error(f"Error loading CNC positions: {str(e)}")
            return {}
    
    def get_reference_index(self, ticker):
        """
        Determine the appropriate reference index for a stock based on its market cap.

        Args:
            ticker (str): Ticker symbol

        Returns:
            str: Reference index ticker symbol
        """
        if ticker in self.small_cap_stocks:
            return self.small_cap_index
        elif ticker in self.mid_cap_stocks:
            return self.mid_cap_index
        elif ticker in self.large_cap_stocks:
            # For large caps, use TOP100CASE index
            return self.large_cap_index
        else:
            # If not explicitly categorized, make a best guess based on naming
            if ticker in ["ACI", "CCL", "RRKABEL", "ELECON"]:
                return self.small_cap_index
            else:
                # Default to mid cap for most stocks
                return self.mid_cap_index

    def load_index_data(self):
        """
        Load historical data for all three indices (SMALLCAP, MIDCAP, and TOP100CASE).
        This data will be used as market benchmarks for regime detection.

        Returns:
            dict: Dictionary with index data
        """
        logger.info("Loading market indices data for regime detection")
        indices = {
            self.small_cap_index: None,
            self.mid_cap_index: None,
            self.large_cap_index: None
        }

        # Load small cap index
        small_cap_data = self.get_historical_data(self.small_cap_index)
        if small_cap_data is not None:
            # Detect market regime for small cap index
            regime, regime_metrics = self.regime_detector.detect_consolidated_regime(small_cap_data)

            indices[self.small_cap_index] = {
                'data': small_cap_data,
                'regime': regime,
                'metrics': regime_metrics,
                'current_regime': regime.iloc[-1] if not regime.empty else MarketRegimeType.UNKNOWN.value
            }
            logger.info(f"Analyzed {self.small_cap_index} market regime: {indices[self.small_cap_index]['current_regime']}")
        else:
            logger.warning(f"Could not load data for {self.small_cap_index}")

        # Load mid cap index
        mid_cap_data = self.get_historical_data(self.mid_cap_index)
        if mid_cap_data is not None:
            # Detect market regime for mid cap index
            regime, regime_metrics = self.regime_detector.detect_consolidated_regime(mid_cap_data)

            indices[self.mid_cap_index] = {
                'data': mid_cap_data,
                'regime': regime,
                'metrics': regime_metrics,
                'current_regime': regime.iloc[-1] if not regime.empty else MarketRegimeType.UNKNOWN.value
            }
            logger.info(f"Analyzed {self.mid_cap_index} market regime: {indices[self.mid_cap_index]['current_regime']}")
        else:
            logger.warning(f"Could not load data for {self.mid_cap_index}")

        # Load large cap index
        large_cap_data = self.get_historical_data(self.large_cap_index)
        if large_cap_data is not None:
            # Detect market regime for large cap index
            regime, regime_metrics = self.regime_detector.detect_consolidated_regime(large_cap_data)

            indices[self.large_cap_index] = {
                'data': large_cap_data,
                'regime': regime,
                'metrics': regime_metrics,
                'current_regime': regime.iloc[-1] if not regime.empty else MarketRegimeType.UNKNOWN.value
            }
            logger.info(f"Analyzed {self.large_cap_index} market regime: {indices[self.large_cap_index]['current_regime']}")
        else:
            logger.warning(f"Could not load data for {self.large_cap_index}")

        # Cache the index data
        self.index_data_cache = indices
        return indices

    def get_historical_data(self, ticker, timeframe=None, days=None):
        """
        Get historical data for a ticker.

        Args:
            ticker (str): Ticker symbol
            timeframe (str): Timeframe/interval for data
            days (int): Number of days to look back

        Returns:
            pd.DataFrame: Historical OHLC data
        """
        timeframe = timeframe or self.atr_timeframe
        days = days or self.lookback_days

        try:
            # Read directly from data files
            file_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'BT', 'data', f'{ticker}_day.csv'
            )

            if os.path.exists(file_path):
                data = pd.read_csv(file_path)

                # Check for date/Date column - case insensitive check
                date_cols = [col for col in data.columns if col.lower() == 'date']
                if date_cols:
                    date_col = date_cols[0]
                else:
                    logger.error(f"No date column found in data for {ticker}")
                    return None

                # Convert to datetime and set as index
                data[date_col] = pd.to_datetime(data[date_col])
                data = data.set_index(date_col)

                # Make sure we don't have more data than requested
                data = data.tail(days * 2)  # Using 2x to account for non-trading days
                logger.info(f"Loaded {len(data)} rows from data file for {ticker}")
            else:
                logger.error(f"No data file found for {ticker}")
                return None

            # Ensure we have enough data
            if data is None or len(data) < 10:
                logger.warning(f"Insufficient data for {ticker}: Got {len(data) if data is not None else 0} points")
                return None

            # Ensure data has required columns (case insensitive)
            required_columns = ['open', 'high', 'low', 'close']
            data_cols_lower = [col.lower() for col in data.columns]

            # Map lowercase columns to actual column names
            col_map = {}
            for req_col in required_columns:
                if req_col in data_cols_lower:
                    col_map[req_col] = data.columns[data_cols_lower.index(req_col)]
                else:
                    logger.error(f"Missing required column {req_col} in data for {ticker}")
                    return None

            # Rename columns to standard format if needed
            if not all(col in data.columns for col in ['Open', 'High', 'Low', 'Close']):
                data = data.rename(columns={
                    col_map['open']: 'Open',
                    col_map['high']: 'High',
                    col_map['low']: 'Low',
                    col_map['close']: 'Close'
                })

            return data

        except Exception as e:
            logger.error(f"Error fetching historical data for {ticker}: {str(e)}")
            return None
    
    def calculate_multiple_stop_loss_methods(self, ticker, position_data):
        """
        Calculate stop loss using multiple methods and provide recommendations.
        Uses appropriate market index as a reference for market regime detection.

        Args:
            ticker (str): Ticker symbol
            position_data (dict): Position data, includes reference_index and reference_regime

        Returns:
            dict: Dictionary with stop loss recommendations and explanations
        """
        try:
            # Extract position details
            entry_price = position_data.get('entry_price', 0)
            current_price = position_data.get('last_price', 0)
            existing_stop_loss = position_data.get('stop_loss', 0)
            stop_loss_source = position_data.get('stop_loss_source', 'unknown')
            position_type = position_data.get('type', 'LONG')

            # Get reference index information
            reference_index = position_data.get('reference_index')
            reference_regime = position_data.get('reference_regime')

            # If current price isn't available in position data, use the last price from historical data
            if current_price == 0:
                data = self.get_historical_data(ticker)
                if data is not None and 'Close' in data.columns:
                    current_price = data['Close'].iloc[-1]
                    logger.info(f"Using latest close price for {ticker}: {current_price}")
                else:
                    logger.error(f"Could not determine current price for {ticker}")
                    return None

            # Get historical data
            data = self.get_historical_data(ticker)
            if data is None:
                logger.warning(f"No historical data available for {ticker}")
                return None

            # Calculate percentage gain/loss
            if entry_price > 0:
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
            else:
                pnl_pct = 0

            # Calculate standard ATR
            atr = self.atr_calculator.calculate_atr(data)
            current_atr = atr.iloc[-1] if not atr.empty else 0

            # Calculate ATR as percentage of price
            atr_pct = (current_atr / current_price) * 100

            # Calculate adaptive ATR (adjusts based on recent volatility)
            adaptive_atr = self.atr_calculator.calculate_adaptive_atr(data)
            adaptive_atr_value = adaptive_atr.iloc[-1] if not adaptive_atr.empty else current_atr

            # Detect individual stock's market regime
            regime, regime_metrics = self.regime_detector.detect_consolidated_regime(data)
            stock_regime = regime.iloc[-1] if not regime.empty else MarketRegimeType.UNKNOWN.value

            # Get volatility and trend metrics
            volatility = regime_metrics['volatility'].iloc[-1] if 'volatility' in regime_metrics else 0
            trend_strength = regime_metrics['trend_strength'].iloc[-1] if 'trend_strength' in regime_metrics else 0

            # Calculate Hurst exponent (trend strength indicator)
            hurst = regime_metrics['hurst'].iloc[-1] if 'hurst' in regime_metrics else 0.5

            # Determine which regime to use for stop loss calculation
            # 1. If we have valid reference index regime, compare it with stock regime
            # 2. If they differ, use a weighted approach
            # 3. If no reference regime available, use stock's own regime

            # Default to stock's own regime
            current_regime = stock_regime
            regime_alignment = "INDIVIDUAL"  # Tracks relationship between stock and index regimes

            # If reference regime available, compare and potentially adjust
            if reference_regime:
                regime_alignment = "MATCH" if stock_regime == reference_regime else "DIFFER"

                # In transitioning markets, trust the index more
                if reference_regime == MarketRegimeType.TRANSITIONING.value:
                    # If index is transitioning but stock seems to have a clearer regime,
                    # use 70% stock regime and 30% index regime influence
                    if stock_regime in [MarketRegimeType.TRENDING_BULLISH.value, MarketRegimeType.TRENDING_BEARISH.value]:
                        # Still use stock's regime but adjust multipliers in weighted calculation
                        current_regime = stock_regime
                        logger.info(f"{ticker} may be leading {reference_index} in trend development")
                    else:
                        # If stock isn't showing clear trend, use index regime
                        current_regime = reference_regime
                        logger.info(f"Using {reference_index} transitioning regime for {ticker}")

                # For trending markets, consider if stock agrees with index trend
                elif reference_regime in [MarketRegimeType.TRENDING_BULLISH.value, MarketRegimeType.TRENDING_BEARISH.value]:
                    if stock_regime == reference_regime:
                        # Strong agreement - use this regime with high confidence
                        current_regime = reference_regime
                        logger.info(f"{ticker} is aligned with {reference_index} {reference_regime} regime")
                    elif stock_regime == MarketRegimeType.TRANSITIONING.value:
                        # Stock may be lagging the index - use index regime with caution
                        current_regime = reference_regime
                        logger.info(f"{ticker} may be lagging {reference_index} in trend development")
                    else:
                        # Stock disagrees with index - trust stock's individual behavior more
                        current_regime = stock_regime
                        logger.info(f"{ticker} shows different regime ({stock_regime}) than {reference_index} ({reference_regime})")

                # For ranging markets, similar approach
                else:
                    if stock_regime == reference_regime:
                        # Agreement on ranging behavior
                        current_regime = reference_regime
                    else:
                        # Stock shows different behavior - trust its own regime more
                        current_regime = stock_regime
                        logger.info(f"{ticker} has different volatility pattern than {reference_index}")

            logger.info(f"Using {current_regime} regime for {ticker} stop loss calculation")

            # Get previous support/resistance levels
            prev_day_low = data['Low'].iloc[-2] if len(data) > 1 else 0
            prev_day_high = data['High'].iloc[-2] if len(data) > 1 else 0

            # Calculate lower support level (previous 5 days)
            if len(data) >= 5:
                support_level = data['Low'].iloc[-5:].min()
            else:
                support_level = prev_day_low

            # Calculate stop losses using different methods

            # Method 1: Fixed ATR multiplier - basic approach
            fixed_atr_multiplier = 2.0  # Standard multiplier
            if position_type.upper() == "LONG":
                fixed_atr_sl = current_price - (fixed_atr_multiplier * current_atr)
            else:
                fixed_atr_sl = current_price + (fixed_atr_multiplier * current_atr)

            # Method 2: Dynamic ATR based on market regime
            regime_multiplier = self.stop_loss_model._get_base_atr_multiplier(
                current_regime,
                PositionType(position_type.upper())
            )

            if position_type.upper() == "LONG":
                dynamic_atr_sl = current_price - (regime_multiplier * current_atr)
            else:
                dynamic_atr_sl = current_price + (regime_multiplier * current_atr)

            # Method 3: Adaptive ATR (accounts for changing volatility)
            if position_type.upper() == "LONG":
                adaptive_atr_sl = current_price - (regime_multiplier * adaptive_atr_value)
            else:
                adaptive_atr_sl = current_price + (regime_multiplier * adaptive_atr_value)

            # Method 4: Support/Resistance based stop loss
            if position_type.upper() == "LONG":
                # Use support level, but ensure minimum distance
                support_distance = current_price - support_level
                min_distance = current_price * (self.min_price_distance_pct / 100)

                if support_distance < min_distance:
                    support_sl = current_price - min_distance
                else:
                    support_sl = support_level
            else:
                # For short positions, use resistance (previous high)
                resistance_distance = prev_day_high - current_price
                min_distance = current_price * (self.min_price_distance_pct / 100)

                if resistance_distance < min_distance:
                    support_sl = current_price + min_distance
                else:
                    support_sl = prev_day_high

            # Method 5: Combined approach (weighted average of methods based on regime)
            # Weight the different methods based on market regime
            weights = {
                MarketRegimeType.TRENDING_BULLISH.value: {'dynamic': 0.5, 'support': 0.3, 'adaptive': 0.2},
                MarketRegimeType.TRENDING_BEARISH.value: {'dynamic': 0.4, 'support': 0.2, 'adaptive': 0.4},
                MarketRegimeType.RANGING_LOW_VOL.value: {'dynamic': 0.3, 'support': 0.5, 'adaptive': 0.2},
                MarketRegimeType.RANGING_HIGH_VOL.value: {'dynamic': 0.2, 'support': 0.3, 'adaptive': 0.5},
                MarketRegimeType.TRANSITIONING.value: {'dynamic': 0.4, 'support': 0.3, 'adaptive': 0.3},
                MarketRegimeType.UNKNOWN.value: {'dynamic': 0.4, 'support': 0.3, 'adaptive': 0.3}
            }

            # Adjust weights if stock and index regimes differ
            if regime_alignment == "DIFFER" and reference_regime:
                # If they differ, slightly favor adaptive ATR which is more responsive to recent changes
                adjusted_weights = {k: dict(v) for k, v in weights.items()}  # Deep copy
                adjusted_weights[current_regime]['adaptive'] += 0.1
                adjusted_weights[current_regime]['dynamic'] -= 0.05
                adjusted_weights[current_regime]['support'] -= 0.05
                regime_weights = adjusted_weights.get(current_regime, adjusted_weights[MarketRegimeType.UNKNOWN.value])
                logger.info(f"Using adjusted weights for {ticker} due to regime difference with {reference_index}")
            else:
                # Use standard weights
                regime_weights = weights.get(current_regime, weights[MarketRegimeType.UNKNOWN.value])

            if position_type.upper() == "LONG":
                combined_sl = (
                    dynamic_atr_sl * regime_weights['dynamic'] +
                    support_sl * regime_weights['support'] +
                    adaptive_atr_sl * regime_weights['adaptive']
                )
            else:
                combined_sl = (
                    dynamic_atr_sl * regime_weights['dynamic'] +
                    support_sl * regime_weights['support'] +
                    adaptive_atr_sl * regime_weights['adaptive']
                )

            # Round all stop loss values to 2 decimal places
            fixed_atr_sl = round(fixed_atr_sl, 2)
            dynamic_atr_sl = round(dynamic_atr_sl, 2)
            adaptive_atr_sl = round(adaptive_atr_sl, 2)
            support_sl = round(support_sl, 2)
            combined_sl = round(combined_sl, 2)

            # Determine final recommendation (the combined approach)
            recommended_sl = combined_sl

            # Determine change from existing stop loss
            if existing_stop_loss > 0:
                sl_change_pct = ((recommended_sl - existing_stop_loss) / existing_stop_loss) * 100
            else:
                sl_change_pct = 0

            # Calculate risk percentages for each method
            if position_type.upper() == "LONG":
                fixed_risk_pct = ((current_price - fixed_atr_sl) / current_price) * 100
                dynamic_risk_pct = ((current_price - dynamic_atr_sl) / current_price) * 100
                adaptive_risk_pct = ((current_price - adaptive_atr_sl) / current_price) * 100
                support_risk_pct = ((current_price - support_sl) / current_price) * 100
                combined_risk_pct = ((current_price - combined_sl) / current_price) * 100
                existing_risk_pct = ((current_price - existing_stop_loss) / current_price) * 100
            else:
                fixed_risk_pct = ((fixed_atr_sl - current_price) / current_price) * 100
                dynamic_risk_pct = ((dynamic_atr_sl - current_price) / current_price) * 100
                adaptive_risk_pct = ((adaptive_atr_sl - current_price) / current_price) * 100
                support_risk_pct = ((support_sl - current_price) / current_price) * 100
                combined_risk_pct = ((combined_sl - current_price) / current_price) * 100
                existing_risk_pct = ((existing_stop_loss - current_price) / current_price) * 100

            # Generate explanations for each method
            fixed_explanation = (
                f"Standard 2.0 × ATR ({current_atr:.2f}) stop loss. "
                f"Risk: {fixed_risk_pct:.2f}% of current price."
            )

            dynamic_explanation = (
                f"Market regime ({current_regime}) based {regime_multiplier:.2f} × ATR stop loss. "
                f"Risk: {dynamic_risk_pct:.2f}% of current price."
            )

            adaptive_explanation = (
                f"Adaptive ATR accounts for recent volatility changes. "
                f"Using multiplier {regime_multiplier:.2f} × adaptive ATR ({adaptive_atr_value:.2f}). "
                f"Risk: {adaptive_risk_pct:.2f}% of current price."
            )

            support_explanation = (
                f"Based on {'support' if position_type.upper() == 'LONG' else 'resistance'} levels "
                f"from previous trading periods. "
                f"Risk: {support_risk_pct:.2f}% of current price."
            )

            # Add reference index information to combined explanation
            index_context = ""
            if reference_regime:
                # Include stock-index relationship in explanation
                if stock_regime == reference_regime:
                    index_context = f" Stock regime matches {reference_index} regime."
                else:
                    index_context = (f" Stock regime ({stock_regime}) differs from "
                                    f"{reference_index} regime ({reference_regime}).")

            combined_explanation = (
                f"Weighted combination based on {current_regime} regime. "
                f"Weights: {regime_weights['dynamic']:.1f} dynamic, "
                f"{regime_weights['support']:.1f} support/resistance, "
                f"{regime_weights['adaptive']:.1f} adaptive. "
                f"Risk: {combined_risk_pct:.2f}% of current price."
                f"{index_context}"
            )

            existing_explanation = (
                f"Current stop loss from {stop_loss_source}. "
                f"Risk: {existing_risk_pct:.2f}% of current price."
            )

            # Compile the results
            result = {
                'ticker': ticker,
                'position_type': position_type,
                'entry_price': entry_price,
                'current_price': current_price,
                'pnl_pct': pnl_pct,
                'reference_index': reference_index,
                'reference_regime': reference_regime,
                'stock_regime': stock_regime,
                'market_regime': current_regime,  # The regime used for calculations
                'regime_alignment': regime_alignment,
                'atr': current_atr,
                'atr_pct': atr_pct,
                'volatility': volatility,
                'trend_strength': trend_strength,
                'hurst_exponent': hurst,

                # Stop loss methods
                'existing_stop_loss': existing_stop_loss,
                'fixed_atr_sl': fixed_atr_sl,
                'dynamic_atr_sl': dynamic_atr_sl,
                'adaptive_atr_sl': adaptive_atr_sl,
                'support_sl': support_sl,
                'recommended_sl': recommended_sl,

                # Risk percentages
                'existing_risk_pct': existing_risk_pct,
                'fixed_risk_pct': fixed_risk_pct,
                'dynamic_risk_pct': dynamic_risk_pct,
                'adaptive_risk_pct': adaptive_risk_pct,
                'support_risk_pct': support_risk_pct,
                'recommended_risk_pct': combined_risk_pct,

                # Explanations
                'existing_explanation': existing_explanation,
                'fixed_explanation': fixed_explanation,
                'dynamic_explanation': dynamic_explanation,
                'adaptive_explanation': adaptive_explanation,
                'support_explanation': support_explanation,
                'recommended_explanation': combined_explanation,

                # Change metrics
                'sl_change_pct': sl_change_pct
            }

            logger.info(f"Calculated stop loss recommendations for {ticker}")
            return result

        except Exception as e:
            logger.error(f"Error calculating stop loss methods for {ticker}: {str(e)}")
            return None
    
    def generate_recommendations(self):
        """
        Generate stop loss recommendations for all CNC positions,
        using appropriate market indices as benchmarks.

        Returns:
            pd.DataFrame: DataFrame with recommendations
        """
        # Load CNC positions
        positions = self.load_cnc_positions()
        if not positions:
            logger.warning("No CNC positions found")
            return None

        # Load and analyze market indices first
        logger.info("Loading market indices for benchmarking...")
        indices = self.load_index_data()

        if not indices or all(idx is None for idx in indices.values()):
            logger.warning("Failed to load market indices - using stock-specific regime detection only")
        else:
            # Log current market regimes
            for index_name, index_data in indices.items():
                if index_data:
                    logger.info(f"{index_name} current market regime: {index_data['current_regime']}")

        logger.info(f"Generating recommendations for {len(positions)} positions")
        results = []

        # Process each position
        for ticker, position_data in positions.items():
            # Determine reference index for this stock
            reference_index = self.get_reference_index(ticker)
            logger.info(f"Processing {ticker} (using {reference_index} as reference index)...")

            # Add reference index to position data
            position_data['reference_index'] = reference_index
            position_data['reference_regime'] = None

            # Add reference index regime information if available
            if reference_index in indices and indices[reference_index] is not None:
                position_data['reference_regime'] = indices[reference_index]['current_regime']
                logger.info(f"  {reference_index} is currently in {position_data['reference_regime']} regime")

            # Calculate stop loss recommendations
            result = self.calculate_multiple_stop_loss_methods(ticker, position_data)
            if result:
                results.append(result)

        if not results:
            logger.warning("No results generated")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(results)

        # Save results to Excel
        try:
            self.save_recommendations_to_excel(df)
        except Exception as e:
            logger.error(f"Error saving recommendations to Excel: {str(e)}")

        return df
    
    def save_recommendations_to_excel(self, df):
        """
        Save recommendations to Excel file with formatted sheets.
        Includes market regime information from reference indices.

        Args:
            df (pd.DataFrame): DataFrame with recommendations
        """
        try:
            # Create Excel writer
            writer = pd.ExcelWriter(self.output_file, engine='xlsxwriter')

            # Create summary sheet with core recommendations
            summary_df = df[['ticker', 'position_type', 'current_price', 'pnl_pct',
                            'reference_index', 'stock_regime', 'market_regime', 'regime_alignment',
                            'existing_stop_loss', 'recommended_sl',
                            'sl_change_pct', 'recommended_risk_pct']]

            summary_df.to_excel(writer, sheet_name='Summary', index=False)

            # Format summary sheet
            workbook = writer.book
            summary_sheet = writer.sheets['Summary']

            # Add formats
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'bg_color': '#D9D9D9',
                'border': 1
            })

            percent_format = workbook.add_format({'num_format': '0.00%'})
            price_format = workbook.add_format({'num_format': '0.00'})

            # Highlight format for regime alignment
            match_format = workbook.add_format({'bg_color': '#C6EFCE'})  # Light green
            differ_format = workbook.add_format({'bg_color': '#FFEB9C'})  # Light yellow

            # Apply formats to summary sheet
            for col_num, value in enumerate(summary_df.columns.values):
                summary_sheet.write(0, col_num, value, header_format)

            # Apply conditional formatting based on regime alignment
            for row_num, row in enumerate(summary_df.values):
                row_num += 1  # Adjust for header row
                for col_num, value in enumerate(row):
                    if col_num == summary_df.columns.get_loc('regime_alignment'):
                        if value == 'MATCH':
                            summary_sheet.write(row_num, col_num, value, match_format)
                        elif value == 'DIFFER':
                            summary_sheet.write(row_num, col_num, value, differ_format)
                        else:
                            summary_sheet.write(row_num, col_num, value)
                    else:
                        # Apply numeric formatting if needed
                        if col_num in [2, 8, 9]:  # price columns
                            summary_sheet.write(row_num, col_num, value, price_format)
                        elif col_num in [3, 10, 11]:  # percentage columns
                            summary_sheet.write(row_num, col_num, value/100, percent_format)
                        else:
                            summary_sheet.write(row_num, col_num, value)

            # Set column widths
            summary_sheet.set_column('A:A', 12)  # ticker
            summary_sheet.set_column('B:B', 10)  # position_type
            summary_sheet.set_column('C:C', 14)  # current_price
            summary_sheet.set_column('D:D', 10)  # pnl_pct
            summary_sheet.set_column('E:E', 15)  # reference_index
            summary_sheet.set_column('F:F', 20)  # stock_regime
            summary_sheet.set_column('G:G', 20)  # market_regime
            summary_sheet.set_column('H:H', 15)  # regime_alignment
            summary_sheet.set_column('I:I', 14)  # existing_stop_loss
            summary_sheet.set_column('J:J', 14)  # recommended_sl
            summary_sheet.set_column('K:K', 10)  # sl_change_pct
            summary_sheet.set_column('L:L', 15)  # recommended_risk_pct

            # Create market regime analysis sheet
            regime_df = df[['ticker', 'reference_index', 'reference_regime', 'stock_regime',
                           'market_regime', 'regime_alignment', 'volatility', 'trend_strength',
                           'hurst_exponent']]

            regime_df.to_excel(writer, sheet_name='Market Regimes', index=False)

            # Format regime sheet
            regime_sheet = writer.sheets['Market Regimes']

            for col_num, value in enumerate(regime_df.columns.values):
                regime_sheet.write(0, col_num, value, header_format)

            # Apply conditional formatting based on regime alignment
            for row_num, row in enumerate(regime_df.values):
                row_num += 1  # Adjust for header row
                for col_num, value in enumerate(row):
                    if col_num == regime_df.columns.get_loc('regime_alignment'):
                        if value == 'MATCH':
                            regime_sheet.write(row_num, col_num, value, match_format)
                        elif value == 'DIFFER':
                            regime_sheet.write(row_num, col_num, value, differ_format)
                        else:
                            regime_sheet.write(row_num, col_num, value)
                    else:
                        regime_sheet.write(row_num, col_num, value)

            # Set column widths for regime sheet
            regime_sheet.set_column('A:A', 12)  # ticker
            regime_sheet.set_column('B:B', 15)  # reference_index
            regime_sheet.set_column('C:E', 20)  # regime columns
            regime_sheet.set_column('F:F', 15)  # regime_alignment
            regime_sheet.set_column('G:I', 12)  # metrics

            # Create detailed methods sheet
            detailed_df = df[['ticker', 'position_type', 'reference_index', 'market_regime', 'current_price',
                              'atr', 'atr_pct', 'volatility', 'trend_strength',
                              'existing_stop_loss', 'fixed_atr_sl', 'dynamic_atr_sl',
                              'adaptive_atr_sl', 'support_sl', 'recommended_sl',
                              'existing_risk_pct', 'fixed_risk_pct', 'dynamic_risk_pct',
                              'adaptive_risk_pct', 'support_risk_pct', 'recommended_risk_pct']]

            detailed_df.to_excel(writer, sheet_name='Detailed Methods', index=False)

            # Format detailed sheet
            detailed_sheet = writer.sheets['Detailed Methods']

            for col_num, value in enumerate(detailed_df.columns.values):
                detailed_sheet.write(0, col_num, value, header_format)

            # Set column widths for detailed sheet
            detailed_sheet.set_column('A:B', 12)
            detailed_sheet.set_column('C:C', 15)
            detailed_sheet.set_column('D:D', 20)
            detailed_sheet.set_column('E:N', 14)  # price columns
            detailed_sheet.set_column('O:U', 14)  # percentage columns

            # Create explanations sheet
            explanations_df = df[['ticker', 'reference_index', 'regime_alignment',
                                 'existing_explanation', 'fixed_explanation',
                                 'dynamic_explanation', 'adaptive_explanation',
                                 'support_explanation', 'recommended_explanation']]

            explanations_df.to_excel(writer, sheet_name='Explanations', index=False)

            # Format explanations sheet
            explanations_sheet = writer.sheets['Explanations']

            for col_num, value in enumerate(explanations_df.columns.values):
                explanations_sheet.write(0, col_num, value, header_format)

            # Set column widths for explanations
            explanations_sheet.set_column('A:A', 12)  # ticker
            explanations_sheet.set_column('B:B', 15)  # reference_index
            explanations_sheet.set_column('C:C', 15)  # regime_alignment
            explanations_sheet.set_column('D:I', 50)  # explanations

            # Save the Excel file
            writer.close()

            logger.info(f"Saved recommendations to {self.output_file}")
            return True

        except Exception as e:
            logger.error(f"Error saving to Excel: {str(e)}")
            return False
    
    def generate_html_report(self, df):
        """
        Generate an HTML report with stop loss recommendations and open it in the browser.

        Args:
            df (pd.DataFrame): DataFrame with recommendations

        Returns:
            str: Path to the generated HTML file
        """
        if df is None or df.empty:
            logger.warning("No recommendations available for HTML report")
            return None

        # Create a timestamp for the filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'ML', 'results'
        )
        os.makedirs(output_dir, exist_ok=True)

        html_file = os.path.join(output_dir, f"cnc_stop_loss_recommendations_{timestamp}.html")

        # Create some simple visualizations for the report

        # 1. Regime distribution pie chart
        plt.figure(figsize=(10, 6))
        regime_counts = df['stock_regime'].value_counts()
        plt.pie(regime_counts, labels=regime_counts.index, autopct='%1.1f%%',
                colors=['lightgreen', 'lightcoral', 'lightskyblue', 'plum', 'wheat'])
        plt.title('Distribution of Stock Market Regimes')
        plt.tight_layout()

        # Convert plot to base64 for HTML embedding
        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        regime_pie_chart = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close()

        # 2. Regime alignment
        plt.figure(figsize=(10, 6))
        alignment_counts = df['regime_alignment'].value_counts()
        plt.bar(alignment_counts.index, alignment_counts, color=['green', 'orange', 'blue'])
        plt.title('Stock-Index Regime Alignment')
        plt.ylabel('Number of Stocks')
        plt.tight_layout()

        # Convert plot to base64
        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        alignment_chart = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close()

        # Start building the HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>CNC Stop Loss Recommendations</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                    color: #333;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 20px;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                    border-radius: 5px;
                }}
                h1, h2, h3 {{
                    color: #2c3e50;
                }}
                h1 {{
                    text-align: center;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #eee;
                }}
                h2 {{
                    margin-top: 30px;
                    padding-bottom: 10px;
                    border-bottom: 1px solid #eee;
                }}
                .section {{
                    margin-bottom: 30px;
                    padding: 20px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
                .trending-bullish {{ background-color: rgba(0, 255, 0, 0.2); }}
                .trending-bearish {{ background-color: rgba(255, 0, 0, 0.2); }}
                .ranging-low-vol {{ background-color: rgba(0, 0, 255, 0.2); }}
                .ranging-high-vol {{ background-color: rgba(255, 0, 255, 0.2); }}
                .transitioning {{ background-color: rgba(255, 165, 0, 0.2); }}
                .unknown {{ background-color: rgba(128, 128, 128, 0.2); }}
                .match {{ color: green; }}
                .differ {{ color: orange; }}
                .charts {{
                    display: flex;
                    flex-wrap: wrap;
                    justify-content: space-between;
                    margin-bottom: 20px;
                }}
                .chart {{
                    width: 48%;
                    margin-bottom: 20px;
                    text-align: center;
                    padding: 10px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    background-color: white;
                }}
                @media (max-width: 768px) {{
                    .chart {{
                        width: 100%;
                    }}
                }}
                .regime-legend {{
                    display: flex;
                    flex-wrap: wrap;
                    margin: 20px 0;
                }}
                .regime-item {{
                    display: flex;
                    align-items: center;
                    margin-right: 20px;
                    margin-bottom: 10px;
                }}
                .regime-color {{
                    width: 20px;
                    height: 20px;
                    margin-right: 5px;
                    border: 1px solid #ccc;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>CNC Stop Loss Recommendations</h1>
                <p style="text-align: center;">Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

                <div class="regime-legend">
                    <h3>Market Regime Legend:</h3>
                    <div class="regime-item">
                        <div class="regime-color trending-bullish"></div>
                        <span>Trending Bullish</span>
                    </div>
                    <div class="regime-item">
                        <div class="regime-color trending-bearish"></div>
                        <span>Trending Bearish</span>
                    </div>
                    <div class="regime-item">
                        <div class="regime-color ranging-low-vol"></div>
                        <span>Ranging Low Volatility</span>
                    </div>
                    <div class="regime-item">
                        <div class="regime-color ranging-high-vol"></div>
                        <span>Ranging High Volatility</span>
                    </div>
                    <div class="regime-item">
                        <div class="regime-color transitioning"></div>
                        <span>Transitioning</span>
                    </div>
                </div>

                <h2>Market Regime Overview</h2>
                <div class="section">
                    <div class="charts">
                        <div class="chart">
                            <h3>Stock Market Regime Distribution</h3>
                            <img src="data:image/png;base64,{regime_pie_chart}" alt="Regime Distribution">
                        </div>
                        <div class="chart">
                            <h3>Stock-Index Regime Alignment</h3>
                            <img src="data:image/png;base64,{alignment_chart}" alt="Regime Alignment">
                        </div>
                    </div>

                    <h3>Current Market Regimes</h3>
                    <table>
                        <tr>
                            <th>Reference Index</th>
                            <th>Current Regime</th>
                        </tr>
        """

        # Add market regime information for each index
        indices = df['reference_index'].unique()
        for index in indices:
            # Get all regimes for this index
            index_regimes = df[df['reference_index'] == index]['reference_regime'].unique()
            for regime in index_regimes:
                if pd.notna(regime):  # Skip NaN values
                    # Convert regime to CSS class
                    regime_class = regime.lower().replace('_', '-') if regime else 'unknown'

                    html_content += f"""
                        <tr>
                            <td>{index}</td>
                            <td class="{regime_class}">{regime}</td>
                        </tr>
                    """

        html_content += """
                    </table>

                    <h3>Stock-Index Regime Alignment</h3>
                    <table>
                        <tr>
                            <th>Alignment</th>
                            <th>Count</th>
                            <th>Percentage</th>
                            <th>Stocks</th>
                        </tr>
        """

        # Add regime alignment statistics
        regime_alignment_counts = df['regime_alignment'].value_counts()
        for alignment, count in regime_alignment_counts.items():
            percentage = (count / len(df)) * 100
            stocks = df[df['regime_alignment'] == alignment]['ticker'].tolist()

            # Convert alignment to CSS class
            alignment_class = alignment.lower()

            html_content += f"""
                        <tr>
                            <td class="{alignment_class}">{alignment}</td>
                            <td>{count}</td>
                            <td>{percentage:.1f}%</td>
                            <td>{', '.join(stocks)}</td>
                        </tr>
            """

        html_content += """
                    </table>
                </div>

                <h2>Stop Loss Recommendations</h2>
        """

        # Group recommendations by reference index
        for index in indices:
            index_df = df[df['reference_index'] == index]

            html_content += f"""
                <div class="section">
                    <h3>Recommendations for {index} Reference Group</h3>
                    <table>
                        <tr>
                            <th>Ticker</th>
                            <th>Position Type</th>
                            <th>Current Price</th>
                            <th>PnL %</th>
                            <th>Stock Regime</th>
                            <th>Existing Stop Loss</th>
                            <th>Recommended Stop Loss</th>
                            <th>Risk %</th>
                            <th>Change %</th>
                        </tr>
            """

            for _, row in index_df.iterrows():
                # Convert regime to CSS class
                regime_class = row['stock_regime'].lower().replace('_', '-') if pd.notna(row['stock_regime']) else 'unknown'
                alignment_class = row['regime_alignment'].lower() if pd.notna(row['regime_alignment']) else ''

                html_content += f"""
                        <tr>
                            <td>{row['ticker']}</td>
                            <td>{row['position_type']}</td>
                            <td>₹{row['current_price']:.2f}</td>
                            <td>{row['pnl_pct']:.2f}%</td>
                            <td class="{regime_class}">{row['stock_regime']}</td>
                            <td>₹{row['existing_stop_loss']:.2f}</td>
                            <td>₹{row['recommended_sl']:.2f}</td>
                            <td>{row['recommended_risk_pct']:.2f}%</td>
                            <td>{row['sl_change_pct']:.2f}%</td>
                        </tr>
                """

            html_content += """
                    </table>
                </div>
            """

        # Add detailed explanations section
        html_content += """
                <h2>Detailed Explanations</h2>
                <div class="section">
                    <table>
                        <tr>
                            <th>Ticker</th>
                            <th>Explanation</th>
                        </tr>
        """

        for _, row in df.iterrows():
            html_content += f"""
                        <tr>
                            <td>{row['ticker']}</td>
                            <td>{row['recommended_explanation']}</td>
                        </tr>
            """

        html_content += """
                    </table>
                </div>
            </div>
        </body>
        </html>
        """

        # Write the HTML content to a file
        with open(html_file, 'w') as f:
            f.write(html_content)

        # Open the HTML file in the default browser
        webbrowser.open('file://' + os.path.realpath(html_file))

        logger.info(f"Generated HTML report: {html_file}")

        return html_file

    def print_recommendations(self, df):
        """
        Print recommendations to console in a formatted table.

        Args:
            df (pd.DataFrame): DataFrame with recommendations
        """
        if df is None or df.empty:
            print("No recommendations available")
            return

        # First print market regime information
        print("\n" + "="*100)
        print("MARKET REGIME ANALYSIS")
        print("="*100)

        # Group by reference index and regime
        indices = df['reference_index'].unique()
        for index in indices:
            # Get all regimes for this index
            index_regimes = df[df['reference_index'] == index]['reference_regime'].unique()
            for regime in index_regimes:
                if pd.notna(regime):  # Skip NaN values
                    print(f"{index} is currently in {regime} regime")

        # Print summary of regime alignment
        regime_alignment_counts = df['regime_alignment'].value_counts()
        print("\nSTOCK-INDEX REGIME ALIGNMENT:")
        for alignment, count in regime_alignment_counts.items():
            percentage = (count / len(df)) * 100
            print(f"  {alignment}: {count} stocks ({percentage:.1f}%)")

            # List stocks in each alignment category
            stocks = df[df['regime_alignment'] == alignment]['ticker'].tolist()
            print(f"    {', '.join(stocks)}")

        # Now print stop loss recommendations
        print("\n" + "="*100)
        print("DYNAMIC STOP LOSS RECOMMENDATIONS")
        print("="*100)

        # Group by reference index
        for index in indices:
            index_df = df[df['reference_index'] == index]
            print(f"\nRECOMMENDATIONS FOR {index} REFERENCE GROUP:")

            # Prepare data for tabulate
            table_data = []
            headers = ["Ticker", "Type", "Current", "PnL %", "Stock Regime",
                      "Current SL", "Recommended SL", "Risk %", "Change %"]

            for _, row in index_df.iterrows():
                # Format regime with match/differ indicator
                if row['regime_alignment'] == "MATCH" and pd.notna(row['reference_regime']):
                    regime_display = f"{row['stock_regime']} (✓)"
                elif row['regime_alignment'] == "DIFFER" and pd.notna(row['reference_regime']):
                    regime_display = f"{row['stock_regime']} (≠)"
                else:
                    regime_display = row['stock_regime']

                table_data.append([
                    row['ticker'],
                    row['position_type'],
                    f"₹{row['current_price']:.2f}",
                    f"{row['pnl_pct']:.2f}%",
                    regime_display,
                    f"₹{row['existing_stop_loss']:.2f}",
                    f"₹{row['recommended_sl']:.2f}",
                    f"{row['recommended_risk_pct']:.2f}%",
                    f"{row['sl_change_pct']:.2f}%"
                ])

            # Print table for this index group
            print(tabulate(table_data, headers=headers, tablefmt="grid"))

        # Add legend for the regime indicators
        print("\nLEGEND:")
        print("  ✓ - Stock regime matches reference index regime")
        print("  ≠ - Stock regime differs from reference index regime")

        print("\nDetailed recommendations saved to:", self.output_file)
        print("="*100 + "\n")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='CNC Stop Loss Recommender')
    
    parser.add_argument('--cnc-file', type=str,
                        help='Path to CNC positions JSON file (defaults to data/cnc_positions.json)')
    parser.add_argument('--output-file', type=str,
                        help='Path to output Excel file')
    
    return parser.parse_args()

def main():
    """Main function"""
    args = parse_arguments()

    try:
        # Initialize recommender
        recommender = CNCStopLossRecommender(
            cnc_file_path=args.cnc_file,
            output_file=args.output_file
        )

        # Generate recommendations
        recommendations = recommender.generate_recommendations()

        # Print to console
        recommender.print_recommendations(recommendations)

        # Generate HTML report
        html_file = recommender.generate_html_report(recommendations)
        logger.info(f"HTML report generated: {html_file}")

        logger.info("Stop loss recommendation process completed")

    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())