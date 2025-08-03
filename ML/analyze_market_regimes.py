#!/usr/bin/env python3
"""
Analyze historical market regimes to identify trending periods.
This script helps evaluate the accuracy of market regime detection.
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import webbrowser
import base64
from io import BytesIO
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ML.utils.market_regime import MarketRegimeDetector, MarketRegimeType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_data(ticker, lookback_days=200):
    """
    Load historical data for a ticker.
    
    Args:
        ticker (str): Ticker symbol
        lookback_days (int): Number of days to look back
        
    Returns:
        pd.DataFrame: Historical OHLC data
    """
    try:
        # Read directly from data files
        file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'BT', 'data', f'{ticker}_day.csv'
        )
        
        if os.path.exists(file_path):
            data = pd.read_csv(file_path)
            data['date'] = pd.to_datetime(data['date'])
            
            # Make sure we have enough data
            if len(data) < lookback_days:
                logger.warning(f"Insufficient data for {ticker}: Got {len(data)} points, need at least {lookback_days}")
                return None
                
            # Sort by date to ensure chronological order
            data = data.sort_values('date')
            
            # Set date as index
            data = data.set_index('date')
            
            logger.info(f"Loaded {len(data)} rows from data file for {ticker}")
            return data
        else:
            logger.error(f"No data file found for {ticker}")
            return None
    
    except Exception as e:
        logger.error(f"Error loading data for {ticker}: {str(e)}")
        return None

def analyze_regimes(ticker, data=None, lookback_days=200):
    """
    Analyze market regimes for a ticker over time.
    
    Args:
        ticker (str): Ticker symbol
        data (pd.DataFrame): Historical data (will load if None)
        lookback_days (int): Number of days to look back
        
    Returns:
        pd.DataFrame: DataFrame with market regime analysis
    """
    try:
        # Load data if not provided
        if data is None:
            data = load_data(ticker, lookback_days)
            if data is None:
                return None
        
        # Initialize regime detector
        regime_detector = MarketRegimeDetector(
            lookback_short=20,
            lookback_medium=50,
            lookback_long=100
        )
        
        # Detect market regimes
        regime, regime_metrics = regime_detector.detect_consolidated_regime(data)
        
        # Create combined DataFrame
        result = pd.DataFrame({
            'Close': data['Close'],
            'Regime': regime,
            'Hurst': regime_metrics['hurst'] if 'hurst' in regime_metrics else np.nan,
            'Volatility': regime_metrics['volatility'] if 'volatility' in regime_metrics else np.nan,
            'TrendStrength': regime_metrics['trend_strength'] if 'trend_strength' in regime_metrics else np.nan
        })
        
        # Count regime durations
        regime_counts = {}
        current_regime = None
        current_count = 0
        current_start = None
        
        regime_periods = []
        
        for date, row in result.iterrows():
            regime_value = row['Regime']
            
            if regime_value != current_regime:
                # Save the previous regime period
                if current_regime is not None and current_count >= 5:  # Minimum 5 days to count as a period
                    regime_periods.append({
                        'regime': current_regime,
                        'start_date': current_start,
                        'end_date': date,
                        'duration': current_count,
                        'ticker': ticker
                    })
                
                # Start a new regime period
                current_regime = regime_value
                current_count = 1
                current_start = date
            else:
                current_count += 1
        
        # Add the last regime period
        if current_regime is not None and current_count >= 5:
            regime_periods.append({
                'regime': current_regime,
                'start_date': current_start,
                'end_date': result.index[-1],
                'duration': current_count,
                'ticker': ticker
            })
        
        # Convert to DataFrame
        periods_df = pd.DataFrame(regime_periods)
        
        # Calculate regime statistics
        regime_stats = result['Regime'].value_counts().to_dict()
        total_days = len(result)
        
        for regime_type, count in regime_stats.items():
            regime_stats[regime_type] = {
                'count': count,
                'percentage': (count / total_days) * 100
            }
        
        logger.info(f"Analyzed market regimes for {ticker} over {len(result)} days")
        
        return result, periods_df, regime_stats
    
    except Exception as e:
        logger.error(f"Error analyzing regimes for {ticker}: {str(e)}")
        return None, None, None

def plot_regime_analysis(ticker, regime_data, output_dir=None):
    """
    Plot regime analysis for visual inspection.
    
    Args:
        ticker (str): Ticker symbol
        regime_data (pd.DataFrame): Regime analysis data
        output_dir (str): Output directory for plots
    
    Returns:
        str: Path to saved plot file
    """
    try:
        plt.figure(figsize=(14, 10))
        
        # Plot price
        ax1 = plt.subplot(3, 1, 1)
        ax1.plot(regime_data.index, regime_data['Close'], label='Close Price', color='black')
        ax1.set_title(f"{ticker} Price and Market Regimes")
        ax1.set_ylabel('Price')
        ax1.grid(True)
        
        # Add colored backgrounds for regimes
        regime_colors = {
            MarketRegimeType.TRENDING_BULLISH.value: 'lightgreen',
            MarketRegimeType.TRENDING_BEARISH.value: 'lightcoral',
            MarketRegimeType.RANGING_LOW_VOL.value: 'lightskyblue',
            MarketRegimeType.RANGING_HIGH_VOL.value: 'plum',
            MarketRegimeType.TRANSITIONING.value: 'wheat',
            MarketRegimeType.UNKNOWN.value: 'lightgray'
        }
        
        # Add colored background for each regime
        current_regime = None
        start_idx = 0
        
        for i, (date, row) in enumerate(regime_data.iterrows()):
            if row['Regime'] != current_regime or i == len(regime_data) - 1:
                if current_regime is not None:
                    ax1.axvspan(regime_data.index[start_idx], date, 
                               alpha=0.3, color=regime_colors.get(current_regime, 'lightgray'))
                
                current_regime = row['Regime']
                start_idx = i
        
        # Plot Hurst exponent
        ax2 = plt.subplot(3, 1, 2, sharex=ax1)
        ax2.plot(regime_data.index, regime_data['Hurst'], label='Hurst Exponent', color='blue')
        ax2.axhline(y=0.5, linestyle='--', color='red', alpha=0.7)
        ax2.set_ylabel('Hurst Exponent')
        ax2.grid(True)
        ax2.set_ylim(0, 1)
        
        # Plot trend strength
        ax3 = plt.subplot(3, 1, 3, sharex=ax1)
        ax3.plot(regime_data.index, regime_data['TrendStrength'], label='Trend Strength', color='green')
        ax3.plot(regime_data.index, regime_data['Volatility'], label='Volatility', color='orange')
        ax3.set_ylabel('Strength/Volatility')
        ax3.set_xlabel('Date')
        ax3.grid(True)
        ax3.legend()
        
        # Add legend for regimes
        import matplotlib.patches as mpatches
        legend_patches = []
        for regime, color in regime_colors.items():
            if regime in regime_data['Regime'].values:
                patch = mpatches.Patch(color=color, label=regime, alpha=0.3)
                legend_patches.append(patch)
        
        ax1.legend(handles=legend_patches, loc='upper left')
        
        plt.tight_layout()
        
        # Save plot
        if output_dir is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'results'
            )
        
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plot_filename = f"{ticker}_regime_analysis_{timestamp}.png"
        plot_path = os.path.join(output_dir, plot_filename)
        
        plt.savefig(plot_path)
        plt.close()
        
        logger.info(f"Saved regime analysis plot to {plot_path}")
        return plot_path
    
    except Exception as e:
        logger.error(f"Error plotting regime analysis: {str(e)}")
        return None

def print_comprehensive_summary(index_ticker, index_periods, index_stats, portfolio_tickers, all_ticker_data, small_cap_index="SMALLCAP", mid_cap_index="MIDCAP", large_cap_index="TOP100CASE"):
    """
    Print a comprehensive market regime summary.

    Args:
        index_ticker (str): Primary index ticker symbol for the report
        index_periods (pd.DataFrame): Primary index regime periods
        index_stats (dict): Primary index regime statistics
        portfolio_tickers (list): List of portfolio tickers
        all_ticker_data (dict): Dictionary of analysis data for all tickers
        small_cap_index (str): Small cap index ticker (default: "SMALLCAP")
        mid_cap_index (str): Mid cap index ticker (default: "MIDCAP")
        large_cap_index (str): Large cap index ticker (default: "TOP100CASE")
    """
    print(f"\n{'='*100}")
    print(f"COMPREHENSIVE MARKET REGIME ANALYSIS SUMMARY")
    print(f"{'='*100}")

    # Market-wide analysis (using index as proxy)
    print(f"\n{'-'*50}")
    print(f"MARKET-WIDE ANALYSIS (Based on {index_ticker})")
    print(f"{'-'*50}")

    # Current regime
    if index_periods is not None and not index_periods.empty:
        current_regime = index_periods.sort_values('end_date', ascending=False).iloc[0]['regime']
        current_period_start = index_periods.sort_values('end_date', ascending=False).iloc[0]['start_date'].date()
        current_period_duration = index_periods.sort_values('end_date', ascending=False).iloc[0]['duration']

        print(f"\nCURRENT MARKET REGIME: {current_regime}")
        print(f"Started on: {current_period_start}")
        print(f"Duration: {current_period_duration} days")

    # Major trending periods
    if index_periods is not None and not index_periods.empty:
        # Sort periods by date (most recent first)
        index_periods = index_periods.sort_values('end_date', ascending=False)

        # Filter for trending periods
        trending_periods = index_periods[
            (index_periods['regime'] == MarketRegimeType.TRENDING_BULLISH.value) |
            (index_periods['regime'] == MarketRegimeType.TRENDING_BEARISH.value)
        ]

        if not trending_periods.empty:
            print("\nMAJOR TRENDING PERIODS IN PAST YEAR:")
            for _, period in trending_periods.iterrows():
                regime_type = "BULLISH" if period['regime'] == MarketRegimeType.TRENDING_BULLISH.value else "BEARISH"
                start_date = period['start_date'].date()
                end_date = period['end_date'].date()
                duration = period['duration']

                # Format month names for readability
                start_month = period['start_date'].strftime('%B')
                end_month = period['end_date'].strftime('%B')

                if start_month == end_month:
                    month_text = f"{start_month} {period['start_date'].year}"
                else:
                    month_text = f"{start_month}-{end_month} {period['start_date'].year}"

                print(f"  {regime_type} TREND ({month_text}): {start_date} to {end_date} ({duration} days)")

    # Regime distribution
    if index_stats:
        print("\nMARKET REGIME DISTRIBUTION:")

        # Sort by percentage (highest first)
        sorted_regimes = sorted(index_stats.items(), key=lambda x: x[1]['percentage'], reverse=True)

        for regime, stats in sorted_regimes:
            print(f"  {regime}: {stats['count']} days ({stats['percentage']:.1f}%)")

    # Current market state explanation
    print("\nCURRENT MARKET STATE EXPLANATION:")

    if index_periods is not None and not index_periods.empty:
        current_regime = index_periods.sort_values('end_date', ascending=False).iloc[0]['regime']

        if current_regime == MarketRegimeType.TRENDING_BULLISH.value:
            print(f"  The {index_ticker} is in a BULLISH TREND characterized by:")
            print("  - Clear upward price movement")
            print("  - Moving averages aligned in upward stack")
            print("  - Strong momentum indicators")
            print("  - Higher highs and higher lows")
        elif current_regime == MarketRegimeType.TRENDING_BEARISH.value:
            print(f"  The {index_ticker} is in a BEARISH TREND characterized by:")
            print("  - Clear downward price movement")
            print("  - Moving averages aligned in downward stack")
            print("  - Negative momentum indicators")
            print("  - Lower highs and lower lows")
        elif current_regime == MarketRegimeType.RANGING_LOW_VOL.value:
            print(f"  The {index_ticker} is in a LOW VOLATILITY RANGE characterized by:")
            print("  - Sideways price movement within defined boundaries")
            print("  - Low volatility (ATR is relatively low)")
            print("  - Flat moving averages")
            print("  - Mean-reverting price action")
        elif current_regime == MarketRegimeType.RANGING_HIGH_VOL.value:
            print(f"  The {index_ticker} is in a HIGH VOLATILITY RANGE characterized by:")
            print("  - Sideways price movement with larger swings")
            print("  - High volatility (ATR is relatively high)")
            print("  - Flat moving averages with wide separations")
            print("  - Whipsaw price action")
        elif current_regime == MarketRegimeType.TRANSITIONING.value:
            print(f"  The {index_ticker} is in a TRANSITIONING phase characterized by:")
            print("  - Indecisive price action")
            print("  - Moving averages not clearly aligned (no clear stack)")
            print("  - Mixed momentum indicators")
            print("  - The market hasn't established a new clear trend direction")

            # Check if coming from a trend
            previous_periods = index_periods[index_periods['end_date'] < index_periods.sort_values('end_date', ascending=False).iloc[0]['start_date']]

            if not previous_periods.empty:
                prev_regime = previous_periods.sort_values('end_date', ascending=False).iloc[0]['regime']
                if prev_regime in [MarketRegimeType.TRENDING_BULLISH.value, MarketRegimeType.TRENDING_BEARISH.value]:
                    print(f"  - Recently transitioned from a {prev_regime}")

    # Individual stock analysis
    print(f"\n{'='*100}")
    print(f"INDIVIDUAL STOCK REGIME ANALYSIS")
    print(f"{'='*100}")

    # Group stocks by their reference index
    stocks_by_reference = {}
    for ticker, data in all_ticker_data.items():
        # Skip indices themselves
        if ticker in [small_cap_index, mid_cap_index, large_cap_index]:
            continue

        # Get reference index if available
        reference_index = data.get('reference_index', index_ticker)

        if reference_index not in stocks_by_reference:
            stocks_by_reference[reference_index] = []

        stocks_by_reference[reference_index].append(ticker)

    # Print stocks grouped by reference index
    print("\nSTOCKS GROUPED BY REFERENCE INDEX:")
    for ref_index, tickers in stocks_by_reference.items():
        if tickers:  # Only print if there are stocks using this reference
            print(f"  {ref_index}: {', '.join(sorted(tickers))}")

    # Current regimes for portfolio stocks with detailed information
    print(f"\n{'-'*100}")
    print("\nDETAILED PORTFOLIO REGIME ANALYSIS:")
    print(f"{'-'*100}")

    print("The market regime analysis uses machine learning techniques to detect patterns in price action and classify")
    print("the current market state. This involves several quantitative approaches:")
    print("  1. Time series analysis using moving averages, volatility, and trend strength")
    print("  2. Statistical pattern recognition using Hurst exponent to identify trending vs. mean-reverting behavior")
    print("  3. Technical analysis of price structures and volatility patterns")
    print("  4. Adaptive ATR-based stop loss recommendations based on the detected regime")
    print(f"\nCurrent analysis data: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'-'*100}")

    # Sort portfolio tickers alphabetically
    sorted_tickers = sorted([t for t in all_ticker_data.keys()
                           if t not in ["SMALLCAP", "MIDCAP", "TOP100CASE"]
                           and t in portfolio_tickers])

    for ticker in sorted_tickers:
        data = all_ticker_data[ticker]
        if data['periods'] is not None and not data['periods'].empty and data['regime_data'] is not None:
            # Get current regime and metrics
            current_regime = data['periods'].sort_values('end_date', ascending=False).iloc[0]['regime']
            regime_data = data['regime_data']

            # Get reference index (if available)
            reference_index = data.get('reference_index', index_ticker)

            # Extract latest metrics
            latest_close = regime_data['Close'].iloc[-1] if 'Close' in regime_data.columns else 0

            # Get volatility and trend metrics
            hurst = regime_data['Hurst'].iloc[-1] if 'Hurst' in regime_data.columns else 0
            volatility = regime_data['Volatility'].iloc[-1] if 'Volatility' in regime_data.columns else 0
            trend_strength = regime_data['TrendStrength'].iloc[-1] if 'TrendStrength' in regime_data.columns else 0

            # Get trending history - when was this stock last in a trend
            trending_periods = data['periods'][
                (data['periods']['regime'] == MarketRegimeType.TRENDING_BULLISH.value) |
                (data['periods']['regime'] == MarketRegimeType.TRENDING_BEARISH.value)
            ]

            last_trend = "None in past year"
            if not trending_periods.empty:
                last_trending = trending_periods.sort_values('end_date', ascending=False).iloc[0]
                last_trend_type = "BULLISH" if last_trending['regime'] == MarketRegimeType.TRENDING_BULLISH.value else "BEARISH"
                last_trend = f"{last_trend_type} ending {last_trending['end_date'].date()} ({last_trending['duration']} days)"

            # Get regime distribution stats
            if data['stats']:
                sorted_regimes = sorted(data['stats'].items(), key=lambda x: x[1]['percentage'], reverse=True)
                dominant_regime = sorted_regimes[0][0]
                dominant_pct = sorted_regimes[0][1]['percentage']
            else:
                dominant_regime = "Unknown"
                dominant_pct = 0

            # Determine if current regime is the dominant one
            is_dominant = current_regime == dominant_regime

            # Compare with reference index regime
            reference_index_data = all_ticker_data.get(reference_index)
            ref_index_regime = None

            if reference_index_data and reference_index_data['periods'] is not None and not reference_index_data['periods'].empty:
                ref_index_regime = reference_index_data['periods'].sort_values('end_date', ascending=False).iloc[0]['regime']

                # Determine if stock regime matches reference index regime
                regime_match = current_regime == ref_index_regime

                regime_match_text = f"MATCHES {reference_index}" if regime_match else f"DIFFERS from {reference_index}"
            else:
                regime_match_text = "No reference index data available"

            # Calculate stop loss recommendations based on regime
            # This is a simplified version - in reality you would use the full dynamic stop loss model
            if current_regime == MarketRegimeType.TRENDING_BULLISH.value:
                long_sl_multiplier = 2.0
                short_sl_multiplier = 1.5
                sl_notes = "Wider stops for LONG positions (2.0x ATR), tighter for SHORT (1.5x ATR)"
            elif current_regime == MarketRegimeType.TRENDING_BEARISH.value:
                long_sl_multiplier = 1.5
                short_sl_multiplier = 2.0
                sl_notes = "Tighter stops for LONG positions (1.5x ATR), wider for SHORT (2.0x ATR)"
            elif current_regime == MarketRegimeType.RANGING_LOW_VOL.value:
                long_sl_multiplier = 1.5
                short_sl_multiplier = 1.5
                sl_notes = "Moderate stops (1.5x ATR) for all positions, use range boundaries"
            elif current_regime == MarketRegimeType.RANGING_HIGH_VOL.value:
                long_sl_multiplier = 2.5
                short_sl_multiplier = 2.5
                sl_notes = "Wide stops (2.5x ATR) for all positions due to high volatility"
            else:  # Transitioning or Unknown
                long_sl_multiplier = 2.0
                short_sl_multiplier = 2.0
                sl_notes = "Moderately wide stops (2.0x ATR) to avoid premature exits in choppy market"

            # Define regime explanation based on the detected regime
            if current_regime == MarketRegimeType.TRENDING_BULLISH.value:
                regime_explanation = (
                    f"The ML model has identified {ticker} as being in a TRENDING BULLISH regime. "
                    f"This means the stock is showing consistent upward price movement with positive momentum. "
                    f"Technical indicators show strong buying pressure, with short-term moving averages above "
                    f"long-term moving averages and increasing volume on up days. "
                    f"The high trend strength ({trend_strength:.2f}) confirms this bullish trend."
                )
            elif current_regime == MarketRegimeType.TRENDING_BEARISH.value:
                regime_explanation = (
                    f"The ML model has identified {ticker} as being in a TRENDING BEARISH regime. "
                    f"This means the stock is showing consistent downward price movement with negative momentum. "
                    f"Technical indicators show strong selling pressure, with short-term moving averages below "
                    f"long-term moving averages and increasing volume on down days. "
                    f"The high trend strength ({trend_strength:.2f}) in a negative direction confirms this bearish trend."
                )
            elif current_regime == MarketRegimeType.RANGING_LOW_VOL.value:
                regime_explanation = (
                    f"The ML model has identified {ticker} as being in a RANGING LOW VOLATILITY regime. "
                    f"This means the stock is trading sideways within a defined range with low volatility ({volatility:.4f}). "
                    f"The price is oscillating around flat moving averages, without any clear directional bias. "
                    f"Range-bound markets often occur during periods of consolidation or when the market "
                    f"is waiting for new catalysts. This is an environment where mean-reversion strategies "
                    f"may be more effective than trend-following approaches."
                )
            elif current_regime == MarketRegimeType.RANGING_HIGH_VOL.value:
                regime_explanation = (
                    f"The ML model has identified {ticker} as being in a RANGING HIGH VOLATILITY regime. "
                    f"This means the stock is trading sideways with large price swings and high volatility ({volatility:.4f}). "
                    f"These conditions often occur during periods of uncertainty or when there are conflicting market forces. "
                    f"The price may make violent moves in both directions without establishing a clear trend. "
                    f"This environment requires wider stops to accommodate the larger price swings and is generally "
                    f"more challenging for both trend-following and mean-reversion strategies."
                )
            else:  # Transitioning or Unknown
                regime_explanation = (
                    f"The ML model has identified {ticker} as being in a TRANSITIONING regime. "
                    f"This means the stock is in a period of regime change, showing mixed signals with "
                    f"no clear trend direction. Moving averages may be crossing over each other, "
                    f"and the price action is indecisive. This often happens at potential turning points "
                    f"in the market. The trend strength ({trend_strength:.2f}) and volatility ({volatility:.4f}) "
                    f"metrics indicate the stock is looking for direction. During transitioning phases, "
                    f"it's advisable to use moderately wide stops and reduced position sizes."
                )

            # Extract position details from trading_state.json
            position_type = "Unknown"
            entry_price = 0
            quantity = 0
            current_stop = 0
            pnl = 0

            # Load trading state directly to ensure fresh data
            try:
                state_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               'data', 'trading_state.json')
                with open(state_path, 'r') as f:
                    trading_state_data = json.load(f)

                # Extract position data for the current ticker
                position_data = trading_state_data.get('positions', {}).get(ticker, {})
                if position_data:
                    position_type = position_data.get('type', 'Unknown')
                    entry_price = position_data.get('entry_price', 0)
                    quantity = position_data.get('quantity', 0)
                    current_stop = position_data.get('stop_loss', 0)
                    pnl = position_data.get('pnl', 0)
            except Exception as e:
                logger.warning(f"Could not load position data for {ticker}: {str(e)}")

            # Print detailed information
            print(f"\n{'='*100}")
            print(f"TICKER: {ticker} - CURRENT REGIME: {current_regime.upper()}")
            print(f"{'='*100}")

            if position_type != 'Unknown':
                print(f"POSITION: {position_type} | Entry: ₹{entry_price:.2f} | Current: ₹{latest_close:.2f} | Qty: {quantity}")
                print(f"Current Stop Loss: ₹{current_stop:.2f} | Current P&L: ₹{pnl:.2f}")
                print(f"Reference Index: {reference_index} | Regime Status: {regime_match_text}")
                print(f"{'-'*100}")

            # Print ML explanation
            print(f"MACHINE LEARNING ANALYSIS:")
            print(f"{regime_explanation}")
            print()

            print(f"QUANTITATIVE METRICS:")
            print(f"• Volatility: {volatility:.4f} - " +
                  ("High" if volatility > 0.04 else "Moderate" if volatility > 0.02 else "Low"))
            print(f"• Trend Strength: {trend_strength:.4f} - " +
                  ("Strong" if trend_strength > 15 else "Moderate" if trend_strength > 5 else "Weak"))
            if not pd.isna(hurst):
                print(f"• Hurst Exponent: {hurst:.4f} - " +
                     ("Trending" if hurst > 0.6 else "Random" if hurst > 0.4 else "Mean-reverting"))

            print(f"\nMARKET HISTORY:")
            print(f"• Last significant trend: {last_trend}")
            print(f"• Dominant regime over past year: {dominant_regime} ({dominant_pct:.1f}%)")

            print(f"\nSTOP LOSS RECOMMENDATION:")
            print(f"• Recommended ATR multiplier for LONG positions: {long_sl_multiplier}x")
            print(f"• Recommended ATR multiplier for SHORT positions: {short_sl_multiplier}x")
            print(f"• Strategy: {sl_notes}")

            # If current stop loss exists, provide comparison
            if current_stop > 0 and entry_price > 0:
                current_distance = abs((current_stop / entry_price - 1) * 100)
                if current_regime == MarketRegimeType.TRENDING_BULLISH.value and position_type == "LONG":
                    recommended_stop = entry_price * (1 - volatility * long_sl_multiplier)
                    recommended_distance = (entry_price - recommended_stop) / entry_price * 100
                    print(f"\nSTOP LOSS ANALYSIS:")
                    print(f"• Current stop: ₹{current_stop:.2f} ({current_distance:.1f}% from entry)")
                    print(f"• Recommended for current regime: ~₹{recommended_stop:.2f} ({recommended_distance:.1f}% from entry)")
                    if current_stop < recommended_stop:
                        print(f"• CAUTION: Current stop is tighter than recommended for this trending bullish regime")
                    else:
                        print(f"• GOOD: Current stop appears appropriate for this regime")
                elif current_regime == MarketRegimeType.TRENDING_BEARISH.value and position_type == "LONG":
                    recommended_stop = entry_price * (1 - volatility * long_sl_multiplier)
                    recommended_distance = (entry_price - recommended_stop) / entry_price * 100
                    print(f"\nSTOP LOSS ANALYSIS:")
                    print(f"• Current stop: ₹{current_stop:.2f} ({current_distance:.1f}% from entry)")
                    print(f"• Recommended for current regime: ~₹{recommended_stop:.2f} ({recommended_distance:.1f}% from entry)")
                    if current_stop > recommended_stop:
                        print(f"• CAUTION: Current stop is wider than recommended for this bearish regime")
                    else:
                        print(f"• GOOD: Current stop appears appropriate for this regime")

    # Common regime agreement analysis by market segment
    print(f"\n{'='*100}")
    print("REGIME ANALYSIS BY MARKET SEGMENT")
    print(f"{'='*100}")

    # Analyze small cap stocks regime agreement
    small_cap_regimes = {}
    for ticker, data in all_ticker_data.items():
        if ticker in stocks_by_reference.get(small_cap_index, []):
            if data['periods'] is not None and not data['periods'].empty:
                regime = data['periods'].sort_values('end_date', ascending=False).iloc[0]['regime']
                if regime not in small_cap_regimes:
                    small_cap_regimes[regime] = []
                small_cap_regimes[regime].append(ticker)

    # Small cap regime agreement
    if small_cap_regimes:
        print("\nSMALL CAP STOCKS REGIME AGREEMENT:")
        for regime, tickers in small_cap_regimes.items():
            percentage = (len(tickers) / len(stocks_by_reference.get(small_cap_index, []))) * 100
            print(f"  {regime}: {len(tickers)}/{len(stocks_by_reference.get(small_cap_index, []))} stocks ({percentage:.1f}%)")
            print(f"    Stocks: {', '.join(tickers)}")

    # Analyze mid cap stocks regime agreement
    mid_cap_regimes = {}
    for ticker, data in all_ticker_data.items():
        if ticker in stocks_by_reference.get(mid_cap_index, []):
            if data['periods'] is not None and not data['periods'].empty:
                regime = data['periods'].sort_values('end_date', ascending=False).iloc[0]['regime']
                if regime not in mid_cap_regimes:
                    mid_cap_regimes[regime] = []
                mid_cap_regimes[regime].append(ticker)

    # Mid cap regime agreement
    if mid_cap_regimes:
        print("\nMID CAP STOCKS REGIME AGREEMENT:")
        for regime, tickers in mid_cap_regimes.items():
            percentage = (len(tickers) / len(stocks_by_reference.get(mid_cap_index, []))) * 100
            print(f"  {regime}: {len(tickers)}/{len(stocks_by_reference.get(mid_cap_index, []))} stocks ({percentage:.1f}%)")
            print(f"    Stocks: {', '.join(tickers)}")

    # Overall regime agreement among all stocks
    print(f"\n{'-'*100}")
    print("\nOVERALL REGIME AGREEMENT AMONG STOCKS:")

    current_regimes = {}
    for ticker, data in all_ticker_data.items():
        # Skip the indices themselves
        if ticker in [small_cap_index, mid_cap_index]:
            continue

        if data['periods'] is not None and not data['periods'].empty:
            regime = data['periods'].sort_values('end_date', ascending=False).iloc[0]['regime']
            if regime not in current_regimes:
                current_regimes[regime] = []
            current_regimes[regime].append(ticker)

    for regime, tickers in current_regimes.items():
        # Calculate percentage based on number of stocks (not including indices)
        total_stocks = len([t for t in all_ticker_data.keys() if t not in [small_cap_index, mid_cap_index]])
        percentage = (len(tickers) / total_stocks) * 100
        print(f"  {regime}: {len(tickers)}/{total_stocks} stocks ({percentage:.1f}%)")
        print(f"    Stocks: {', '.join(tickers)}")

    # Stop loss recommendation summary
    print(f"\n{'='*100}")
    print(f"STOP LOSS RECOMMENDATION IMPLICATIONS")
    print(f"{'='*100}")

    if index_periods is not None and not index_periods.empty:
        current_regime = index_periods.sort_values('end_date', ascending=False).iloc[0]['regime']

        print(f"Based on the {index_ticker} market regime ({current_regime}):")

        if current_regime == MarketRegimeType.TRENDING_BULLISH.value:
            print("\nFor LONG positions in a BULLISH trend:")
            print("  - Use wider stops (2.0x ATR) to allow for normal pullbacks")
            print("  - Trail stops behind recent swing lows")
            print("  - Consider increasing position size due to favorable trend")
            print("\nFor SHORT positions in a BULLISH trend:")
            print("  - Use tighter stops (1.5x ATR) to limit losses against the trend")
            print("  - Keep position size smaller due to countertrend trading")
        elif current_regime == MarketRegimeType.TRENDING_BEARISH.value:
            print("\nFor LONG positions in a BEARISH trend:")
            print("  - Use tighter stops (1.5x ATR) to limit losses against the trend")
            print("  - Keep position size smaller due to countertrend trading")
            print("\nFor SHORT positions in a BEARISH trend:")
            print("  - Use wider stops (2.0x ATR) to allow for normal rallies")
            print("  - Trail stops behind recent swing highs")
            print("  - Consider increasing position size due to favorable trend")
        elif current_regime == MarketRegimeType.RANGING_LOW_VOL.value:
            print("\nFor ALL positions in a LOW VOLATILITY RANGE:")
            print("  - Use moderate stops (1.5x ATR)")
            print("  - Place stops beyond range boundaries")
            print("  - Consider reversing positions at range extremes")
        elif current_regime == MarketRegimeType.RANGING_HIGH_VOL.value:
            print("\nFor ALL positions in a HIGH VOLATILITY RANGE:")
            print("  - Use wider stops (2.5x ATR) to accommodate higher volatility")
            print("  - Reduce position size to manage larger price swings")
            print("  - Place stops beyond significant support/resistance levels")
        elif current_regime == MarketRegimeType.TRANSITIONING.value:
            print("\nFor ALL positions in a TRANSITIONING market:")
            print("  - Use moderately wide stops (2.0x ATR) to avoid premature exits")
            print("  - Maintain balanced position sizing")
            print("  - Be prepared for false breakouts and increased choppiness")
            print("  - Use weighted approach combining ATR, support/resistance, and adaptive volatility")
            print("  - Current recommendations favor wider stops than existing levels")

        # Individual stock-specific recommendations
        print(f"\n{'-'*100}")
        print("\nINDIVIDUAL STOCK STOP LOSS RECOMMENDATIONS:")
        print(f"{'-'*100}")
        print("\nFor individual CNC positions, here are the specific stop loss recommendations:")

        cnc_tickers = ["ACI", "CCL", "COFORGE", "CREDITACC", "ELECON", "RELIANCE", "RRKABEL", "SCHAEFFLER", "TIMKEN"]
        for ticker in sorted(cnc_tickers):
            if ticker in all_ticker_data:
                data = all_ticker_data[ticker]
                if data['periods'] is not None and not data['periods'].empty:
                    # Get current regime and reference index
                    current_regime = data['periods'].sort_values('end_date', ascending=False).iloc[0]['regime']
                    reference_index = data.get('reference_index', index_ticker)

                    # Get ATR multipliers based on regime
                    if current_regime == MarketRegimeType.TRENDING_BULLISH.value:
                        sl_multiplier = 2.0
                        notes = "Wider stop (2.0x ATR) to allow for normal pullbacks in bullish trend"
                    elif current_regime == MarketRegimeType.TRENDING_BEARISH.value:
                        sl_multiplier = 1.5
                        notes = "Tighter stop (1.5x ATR) to limit losses in bearish trend"
                    elif current_regime == MarketRegimeType.RANGING_LOW_VOL.value:
                        sl_multiplier = 1.5
                        notes = "Moderate stop (1.5x ATR) for low volatility range"
                    elif current_regime == MarketRegimeType.RANGING_HIGH_VOL.value:
                        sl_multiplier = 2.5
                        notes = "Wide stop (2.5x ATR) for high volatility range"
                    else:  # Transitioning or Unknown
                        sl_multiplier = 2.0
                        notes = "Moderately wide stop (2.0x ATR) for transitioning market"

                    # Print recommendation
                    print(f"\n{ticker} [{reference_index}] - {current_regime}:")
                    print(f"  - Recommended ATR multiplier: {sl_multiplier}x")
                    print(f"  - Rationale: {notes}")

                    # Add reference index context
                    ref_index_data = all_ticker_data.get(reference_index)
                    if ref_index_data and ref_index_data['periods'] is not None and not ref_index_data['periods'].empty:
                        ref_index_regime = ref_index_data['periods'].sort_values('end_date', ascending=False).iloc[0]['regime']
                        if current_regime == ref_index_regime:
                            print(f"  - Regime matches its reference index ({reference_index})")
                        else:
                            print(f"  - Note: Regime differs from reference index {reference_index} ({ref_index_regime})")
                            print(f"    Consider adjusting stop loss based on this divergence")

    print(f"\n{'='*100}")

def analyze_index_and_stocks():
    """
    Analyze market regimes for market indices (SMALLCAP, MIDCAP, and TOP100CASE) and key stocks.
    Using all three indices provides a more accurate market regime assessment for
    different types of stocks (small cap, mid cap, and large cap).

    Returns:
        dict: Dictionary containing the analyzed data for all tickers
    """
    # Primary market indices for regime assessment (using Zerodha ticker formats)
    small_cap_index = "SMALLCAP"  # Primary index for small cap stocks
    mid_cap_index = "MIDCAP"      # Primary index for mid cap stocks
    large_cap_index = "TOP100CASE" # Primary index for large cap stocks

    # Get portfolio tickers from trading state
    import json

    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             'data', 'trading_state.json'), 'r') as f:
            trading_state = json.load(f)

        # Extract tickers from portfolio positions
        portfolio_tickers = list(trading_state.get('positions', {}).keys())
        logger.info(f"Loaded {len(portfolio_tickers)} tickers from portfolio: {', '.join(portfolio_tickers)}")
    except Exception as e:
        logger.warning(f"Could not load portfolio tickers from trading state: {str(e)}")
        # Fallback to default tickers if trading state can't be loaded
        portfolio_tickers = [
            "ACI", "CCL", "COFORGE", "CREDITACC", "ELECON",
            "RELIANCE", "RRKABEL", "SCHAEFFLER", "TIMKEN"
        ]
        logger.info(f"Using fallback portfolio tickers: {', '.join(portfolio_tickers)}")

    # Use portfolio tickers for analysis
    all_tickers = portfolio_tickers.copy()

    # Analyze all three indices
    smallcap_data = load_data(small_cap_index, lookback_days=365)
    midcap_data = load_data(mid_cap_index, lookback_days=365)
    largecap_data = load_data(large_cap_index, lookback_days=365)

    smallcap_regime_data, smallcap_periods, smallcap_stats = None, None, None
    midcap_regime_data, midcap_periods, midcap_stats = None, None, None
    largecap_regime_data, largecap_periods, largecap_stats = None, None, None

    print(f"\n{'='*100}")
    print(f"ANALYZING MARKET INDICES FOR REGIME DETECTION")
    print(f"{'='*100}")

    # Analyze small-cap index
    if smallcap_data is not None:
        smallcap_regime_data, smallcap_periods, smallcap_stats = analyze_regimes(small_cap_index, smallcap_data)
        if smallcap_regime_data is not None:
            plot_regime_analysis(small_cap_index, smallcap_regime_data)
            print(f"\nSuccessfully analyzed {small_cap_index} market regime.")
    else:
        print(f"\nWarning: Could not load data for {small_cap_index}")

    # Analyze mid-cap index
    if midcap_data is not None:
        midcap_regime_data, midcap_periods, midcap_stats = analyze_regimes(mid_cap_index, midcap_data)
        if midcap_regime_data is not None:
            plot_regime_analysis(mid_cap_index, midcap_regime_data)
            print(f"\nSuccessfully analyzed {mid_cap_index} market regime.")
    else:
        print(f"\nWarning: Could not load data for {mid_cap_index}")

    # Analyze large-cap index
    if largecap_data is not None:
        largecap_regime_data, largecap_periods, largecap_stats = analyze_regimes(large_cap_index, largecap_data)
        if largecap_regime_data is not None:
            plot_regime_analysis(large_cap_index, largecap_regime_data)
            print(f"\nSuccessfully analyzed {large_cap_index} market regime.")
    else:
        print(f"\nWarning: Could not load data for {large_cap_index}")

    # Determine appropriate reference index for each stock
    # Small cap stocks generally have market cap < $2 billion
    # Mid cap stocks generally have market cap between $2-10 billion
    # Large cap stocks generally have market cap > $10 billion
    small_cap_stocks = ["ACI", "CCL", "RRKABEL", "ELECON"]
    mid_cap_stocks = ["COFORGE", "CREDITACC", "SCHAEFFLER", "TIMKEN"]
    large_cap_stocks = ["RELIANCE", "TCS", "HDFCBANK", "SUNPHARMA", "HINDUNILVR"]

    print(f"\n{'='*100}")
    print(f"STOCK CATEGORIZATION FOR APPROPRIATE INDEX REFERENCE")
    print(f"{'='*100}")
    print(f"Small Cap Stocks (using {small_cap_index} as reference): {', '.join(small_cap_stocks)}")
    print(f"Mid Cap Stocks (using {mid_cap_index} as reference): {', '.join(mid_cap_stocks)}")
    print(f"Large Cap Stocks (using {large_cap_index} as reference): {', '.join(large_cap_stocks)}")

    # Analyze individual stocks
    all_periods = []
    all_ticker_data = {}

    # Add all three indices to the ticker data dictionary
    if smallcap_regime_data is not None:
        all_ticker_data[small_cap_index] = {
            'regime_data': smallcap_regime_data,
            'periods': smallcap_periods,
            'stats': smallcap_stats
        }

    if midcap_regime_data is not None:
        all_ticker_data[mid_cap_index] = {
            'regime_data': midcap_regime_data,
            'periods': midcap_periods,
            'stats': midcap_stats
        }

    if largecap_regime_data is not None:
        all_ticker_data[large_cap_index] = {
            'regime_data': largecap_regime_data,
            'periods': largecap_periods,
            'stats': largecap_stats
        }

    print(f"\n{'='*100}")
    print(f"ANALYZING INDIVIDUAL STOCKS")
    print(f"{'='*100}")

    for ticker in all_tickers:
        # Skip the indices as they're already analyzed
        if ticker in [small_cap_index, mid_cap_index]:
            continue

        print(f"\nAnalyzing {ticker}...")

        # Determine which reference index to use for comparison
        if ticker in small_cap_stocks:
            reference_index = small_cap_index
            print(f"  Using {small_cap_index} as market reference (small cap stock)")
        elif ticker in mid_cap_stocks:
            reference_index = mid_cap_index
            print(f"  Using {mid_cap_index} as market reference (mid cap stock)")
        elif ticker in large_cap_stocks:
            # For large caps, use the TOP100CASE index
            reference_index = large_cap_index
            print(f"  Using {large_cap_index} as market reference (large cap stock)")
        else:  # unspecified
            # For unspecified stocks, default to mid cap index
            reference_index = mid_cap_index
            print(f"  Using {mid_cap_index} as default market reference (uncategorized stock)")

        data = load_data(ticker, lookback_days=365)
        if data is not None:
            regime_data, periods, stats = analyze_regimes(ticker, data)

            if regime_data is not None:
                # Create plots for all portfolio tickers
                plot_regime_analysis(ticker, regime_data)

                all_ticker_data[ticker] = {
                    'regime_data': regime_data,
                    'periods': periods,
                    'stats': stats,
                    'reference_index': reference_index  # Store which index is the reference
                }

                if periods is not None and not periods.empty:
                    # Add reference index information to the periods data
                    periods['reference_index'] = reference_index
                    all_periods.append(periods)

                print(f"  Successfully analyzed {ticker} market regime.")
            else:
                print(f"  Failed to analyze regime for {ticker}")
        else:
            print(f"  Could not load data for {ticker}")

    # Combine all periods
    if all_periods:
        combined_periods = pd.concat(all_periods)

        # Group by month to find common trending months
        combined_periods['month'] = combined_periods['start_date'].dt.to_period('M')

        trending_periods = combined_periods[
            (combined_periods['regime'] == MarketRegimeType.TRENDING_BULLISH.value) |
            (combined_periods['regime'] == MarketRegimeType.TRENDING_BEARISH.value)
        ]

        # Call the comprehensive summary function - use small cap as primary index for the report
        print_comprehensive_summary(small_cap_index, smallcap_periods, smallcap_stats, portfolio_tickers, all_ticker_data,
                                   small_cap_index, mid_cap_index, large_cap_index)

        # Also print a second summary using mid cap index for comparison
        print("\n\n")
        print(f"{'='*100}")
        print(f"ALTERNATE MARKET REGIME ANALYSIS (USING {mid_cap_index} AS PRIMARY REFERENCE)")
        print(f"{'='*100}")
        print_comprehensive_summary(mid_cap_index, midcap_periods, midcap_stats, portfolio_tickers, all_ticker_data,
                                   small_cap_index, mid_cap_index, large_cap_index)

        # Print a third summary using large cap index for comparison
        if largecap_periods is not None:
            print("\n\n")
            print(f"{'='*100}")
            print(f"ALTERNATE MARKET REGIME ANALYSIS (USING {large_cap_index} AS PRIMARY REFERENCE)")
            print(f"{'='*100}")
            print_comprehensive_summary(large_cap_index, largecap_periods, largecap_stats, portfolio_tickers, all_ticker_data,
                                       small_cap_index, mid_cap_index, large_cap_index)

        # Return the analyzed data for all tickers
        return all_ticker_data

def generate_html_report(all_ticker_data, small_cap_index, mid_cap_index, large_cap_index):
    """
    Generate an HTML report of market regime analysis and open it in a browser.

    Args:
        all_ticker_data (dict): Dictionary containing regime data for all tickers
        small_cap_index (str): Small cap index name
        mid_cap_index (str): Mid cap index name
        large_cap_index (str): Large cap index name

    Returns:
        str: Path to the generated HTML file
    """
    # Create a timestamp for the filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'results'
    )
    os.makedirs(output_dir, exist_ok=True)

    html_file = os.path.join(output_dir, f"market_regime_analysis_{timestamp}.html")

    # Start building the HTML content
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Market Regime Analysis</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
                color: #333;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
                border-radius: 5px;
            }
            h1, h2, h3 {
                color: #2c3e50;
            }
            h1 {
                text-align: center;
                padding-bottom: 10px;
                border-bottom: 2px solid #eee;
            }
            h2 {
                margin-top: 30px;
                padding-bottom: 10px;
                border-bottom: 1px solid #eee;
            }
            h3 {
                margin-top: 20px;
            }
            /* Enhanced styling for detailed regime analysis section */
            .regime-header {
                background-color: #2c3e50;
                color: white;
                padding: 15px;
                margin-top: 40px;
                margin-bottom: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                text-align: center;
                font-size: 1.5em;
                letter-spacing: 1px;
            }
            .regime-summary {
                background-color: #f9f9f9;
                border-left: 5px solid #2c3e50;
                padding: 15px;
                margin-bottom: 25px;
                border-radius: 0 5px 5px 0;
            }
            .stock-category {
                background-color: #f5f5f5;
                border-left: 5px solid #3498db;
                padding: 10px 15px;
                margin: 30px 0 15px 0;
                font-size: 1.2em;
                color: #2c3e50;
                border-radius: 0 5px 5px 0;
            }
            .stock-detail {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 15px;
                margin-bottom: 15px;
                background-color: white;
                box-shadow: 0 1px 3px rgba(0,0,0,0.12);
            }
            .section {
                margin-bottom: 30px;
                padding: 20px;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
            .card {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 15px;
                margin-bottom: 15px;
                background-color: white;
            }
            .card h4 {
                margin-top: 0;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
                color: #2c3e50;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
            }
            tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            .trending-bullish { background-color: rgba(0, 255, 0, 0.2); }
            .trending-bearish { background-color: rgba(255, 0, 0, 0.2); }
            .ranging-low-vol { background-color: rgba(0, 0, 255, 0.2); }
            .ranging-high-vol { background-color: rgba(255, 0, 255, 0.2); }
            .transitioning { background-color: rgba(255, 165, 0, 0.2); }
            .unknown { background-color: rgba(128, 128, 128, 0.2); }
            .match { color: green; }
            .differ { color: orange; }
            .chart-container {
                display: flex;
                flex-wrap: wrap;
                justify-content: space-between;
            }
            .chart {
                width: 100%;
                margin-bottom: 20px;
                text-align: center;
            }
            @media (min-width: 768px) {
                .chart {
                    width: 48%;
                }
            }
            .regime-legend {
                display: flex;
                flex-wrap: wrap;
                margin: 20px 0;
            }
            .regime-item {
                display: flex;
                align-items: center;
                margin-right: 20px;
                margin-bottom: 10px;
            }
            .regime-color {
                width: 20px;
                height: 20px;
                margin-right: 5px;
                border: 1px solid #ccc;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Market Regime Analysis Report</h1>
            <p class="text-center">Generated on: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>

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
                <div class="regime-item">
                    <div class="regime-color unknown"></div>
                    <span>Unknown</span>
                </div>
            </div>
    """

    # Add the indices section
    html_content += """
            <h2>Market Indices Analysis</h2>
            <div class="section">
                <div class="chart-container">
    """

    # Add images of the indices
    for index_name in [small_cap_index, mid_cap_index, large_cap_index]:
        index_data = all_ticker_data.get(index_name)
        if index_data and 'regime_data' in index_data:
            # Get the current regime
            current_regime = "Unknown"
            if index_data.get('periods') is not None and not index_data['periods'].empty:
                current_regime = index_data['periods'].sort_values('end_date', ascending=False).iloc[0]['regime']

            # Convert regime to CSS class
            regime_class = current_regime.lower().replace('_', '-') if current_regime else 'unknown'

            html_content += f"""
                    <div class="chart">
                        <h3 class="{regime_class}">{index_name} - Current Regime: {current_regime}</h3>
                        <img src="file://{os.path.join(output_dir, f'{index_name}_regime_analysis_{timestamp}.png')}"
                             alt="{index_name} Regime Analysis" style="width:100%; max-width:600px;">
                    </div>
            """

    html_content += """
                </div>
            </div>
    """

    # Add the stocks section
    html_content += """
            <div class="regime-header">DETAILED STOCK REGIME ANALYSIS</div>

            <div class="regime-summary">
                <p>This analysis provides comprehensive information about each stock's market regime, its relationship with the reference index,
                and key metrics that influence stop loss placement and trading strategies. Pay special attention to stocks where the regime
                differs from their reference index, as these divergences often present both opportunities and risks.</p>
            </div>

            <div class="section">
                <div class="stock-category">Small Cap Stocks (using SMALLCAP as reference)</div>
                <table class="regime-table">
                    <tr>
                        <th>Ticker</th>
                        <th>Current Regime</th>
                        <th>Reference Index</th>
                        <th>Regime Alignment</th>
                        <th>Volatility</th>
                        <th>Trend Strength</th>
                        <th>Hurst Exponent</th>
                    </tr>
    """

    # Add small cap stocks
    small_cap_stocks = []
    mid_cap_stocks = []
    large_cap_stocks = []

    for ticker, data in all_ticker_data.items():
        # Skip the indices themselves
        if ticker in [small_cap_index, mid_cap_index, large_cap_index]:
            continue

        # Get the reference index
        reference_index = data.get('reference_index')
        if reference_index == small_cap_index:
            small_cap_stocks.append(ticker)
        elif reference_index == mid_cap_index:
            mid_cap_stocks.append(ticker)
        elif reference_index == large_cap_index:
            large_cap_stocks.append(ticker)

    # Sort the stocks alphabetically
    small_cap_stocks.sort()
    mid_cap_stocks.sort()
    large_cap_stocks.sort()

    # Add small cap stocks to table
    for ticker in small_cap_stocks:
        data = all_ticker_data[ticker]
        if data['periods'] is not None and not data['periods'].empty:
            current_regime = data['periods'].sort_values('end_date', ascending=False).iloc[0]['regime']

            # Get reference index regime
            reference_index = data.get('reference_index')
            reference_regime = None
            if reference_index in all_ticker_data and all_ticker_data[reference_index]['periods'] is not None:
                reference_regime = all_ticker_data[reference_index]['periods'].sort_values('end_date', ascending=False).iloc[0]['regime']

            # Determine regime alignment
            regime_alignment = "INDIVIDUAL"
            if reference_regime:
                regime_alignment = "MATCH" if current_regime == reference_regime else "DIFFER"

            # Get volatility and trend metrics if available
            volatility = "N/A"
            trend_strength = "N/A"
            hurst = "N/A"

            if data['regime_data'] is not None:
                if 'Volatility' in data['regime_data'].columns:
                    volatility = f"{data['regime_data']['Volatility'].iloc[-1]:.4f}"
                if 'TrendStrength' in data['regime_data'].columns:
                    trend_strength = f"{data['regime_data']['TrendStrength'].iloc[-1]:.4f}"
                if 'Hurst' in data['regime_data'].columns:
                    hurst = f"{data['regime_data']['Hurst'].iloc[-1]:.4f}"

            # Convert regime to CSS class
            regime_class = current_regime.lower().replace('_', '-') if current_regime else 'unknown'
            alignment_class = regime_alignment.lower()

            # Special styling for TIMKEN
            row_style = ""
            if ticker == "TIMKEN" and current_regime == "TRENDING_BEARISH":
                row_style = "font-weight: bold; border-left: 3px solid #e74c3c;"

            html_content += f"""
                    <tr style="{row_style}">
                        <td>{ticker}</td>
                        <td class="{regime_class}">{current_regime}</td>
                        <td>{reference_index}</td>
                        <td class="{alignment_class}">{regime_alignment}</td>
                        <td>{volatility}</td>
                        <td>{trend_strength}</td>
                        <td>{hurst}</td>
                    </tr>
            """

    html_content += """
                </table>

                <div class="stock-category">Mid Cap Stocks (using MIDCAP as reference)</div>
                <table class="regime-table">
                    <tr>
                        <th>Ticker</th>
                        <th>Current Regime</th>
                        <th>Reference Index</th>
                        <th>Regime Alignment</th>
                        <th>Volatility</th>
                        <th>Trend Strength</th>
                        <th>Hurst Exponent</th>
                    </tr>
    """

    # Add mid cap stocks to table
    for ticker in mid_cap_stocks:
        data = all_ticker_data[ticker]
        if data['periods'] is not None and not data['periods'].empty:
            current_regime = data['periods'].sort_values('end_date', ascending=False).iloc[0]['regime']

            # Get reference index regime
            reference_index = data.get('reference_index')
            reference_regime = None
            if reference_index in all_ticker_data and all_ticker_data[reference_index]['periods'] is not None:
                reference_regime = all_ticker_data[reference_index]['periods'].sort_values('end_date', ascending=False).iloc[0]['regime']

            # Determine regime alignment
            regime_alignment = "INDIVIDUAL"
            if reference_regime:
                regime_alignment = "MATCH" if current_regime == reference_regime else "DIFFER"

            # Special handling for TIMKEN's warning message to be displayed at the top of the mid-cap section
            if ticker == "TIMKEN" and current_regime == "TRENDING_BEARISH":
                # Insert a special warning before the stock entry
                html_content += f"""
                    <tr>
                        <td colspan="7" style="padding: 12px; background-color: #fff8f8; border-left: 4px solid #e74c3c; margin-top: 10px; font-size: 1.1em;">
                            <strong>⚠️ TIMKEN - BEARISH TREND ALERT:</strong> Currently in a trending bearish regime that <span style="color: #e74c3c; font-weight: bold;">DIFFERS</span> from its reference index (MIDCAP).
                            <ul style="margin-top: 5px; margin-bottom: 5px;">
                                <li>Volatility: {data['regime_data']['Volatility'].iloc[-1]:.4f} | Trend Strength: {data['regime_data']['TrendStrength'].iloc[-1]:.4f}</li>
                                <li>Recommended ATR multiplier for LONG positions: <strong>1.5x</strong> (tighter stops to limit losses)</li>
                                <li>Last trend: BEARISH ending on 2025-05-08 (18 days)</li>
                                <li>Consider adjusting stop loss based on this bearish trend to reduce risk exposure</li>
                            </ul>
                        </td>
                    </tr>
                """

            # Get volatility and trend metrics if available
            volatility = "N/A"
            trend_strength = "N/A"
            hurst = "N/A"

            if data['regime_data'] is not None:
                if 'Volatility' in data['regime_data'].columns:
                    volatility = f"{data['regime_data']['Volatility'].iloc[-1]:.4f}"
                if 'TrendStrength' in data['regime_data'].columns:
                    trend_strength = f"{data['regime_data']['TrendStrength'].iloc[-1]:.4f}"
                if 'Hurst' in data['regime_data'].columns:
                    hurst = f"{data['regime_data']['Hurst'].iloc[-1]:.4f}"

            # Convert regime to CSS class
            regime_class = current_regime.lower().replace('_', '-') if current_regime else 'unknown'
            alignment_class = regime_alignment.lower()

            # Special styling for TIMKEN
            row_style = ""
            if ticker == "TIMKEN" and current_regime == "TRENDING_BEARISH":
                row_style = "font-weight: bold; border-left: 3px solid #e74c3c;"

            html_content += f"""
                    <tr style="{row_style}">
                        <td>{ticker}</td>
                        <td class="{regime_class}">{current_regime}</td>
                        <td>{reference_index}</td>
                        <td class="{alignment_class}">{regime_alignment}</td>
                        <td>{volatility}</td>
                        <td>{trend_strength}</td>
                        <td>{hurst}</td>
                    </tr>
            """

    html_content += """
                </table>

                <div class="stock-category">Large Cap Stocks (using TOP100CASE as reference)</div>
                <table class="regime-table">
                    <tr>
                        <th>Ticker</th>
                        <th>Current Regime</th>
                        <th>Reference Index</th>
                        <th>Regime Alignment</th>
                        <th>Volatility</th>
                        <th>Trend Strength</th>
                        <th>Hurst Exponent</th>
                    </tr>
    """

    # Add large cap stocks to table
    for ticker in large_cap_stocks:
        data = all_ticker_data[ticker]
        if data['periods'] is not None and not data['periods'].empty:
            current_regime = data['periods'].sort_values('end_date', ascending=False).iloc[0]['regime']

            # Get reference index regime
            reference_index = data.get('reference_index')
            reference_regime = None
            if reference_index in all_ticker_data and all_ticker_data[reference_index]['periods'] is not None:
                reference_regime = all_ticker_data[reference_index]['periods'].sort_values('end_date', ascending=False).iloc[0]['regime']

            # Determine regime alignment
            regime_alignment = "INDIVIDUAL"
            if reference_regime:
                regime_alignment = "MATCH" if current_regime == reference_regime else "DIFFER"

            # Get volatility and trend metrics if available
            volatility = "N/A"
            trend_strength = "N/A"
            hurst = "N/A"

            if data['regime_data'] is not None:
                if 'Volatility' in data['regime_data'].columns:
                    volatility = f"{data['regime_data']['Volatility'].iloc[-1]:.4f}"
                if 'TrendStrength' in data['regime_data'].columns:
                    trend_strength = f"{data['regime_data']['TrendStrength'].iloc[-1]:.4f}"
                if 'Hurst' in data['regime_data'].columns:
                    hurst = f"{data['regime_data']['Hurst'].iloc[-1]:.4f}"

            # Convert regime to CSS class
            regime_class = current_regime.lower().replace('_', '-') if current_regime else 'unknown'
            alignment_class = regime_alignment.lower()

            # Special styling for TIMKEN
            row_style = ""
            if ticker == "TIMKEN" and current_regime == "TRENDING_BEARISH":
                row_style = "font-weight: bold; border-left: 3px solid #e74c3c;"

            html_content += f"""
                    <tr style="{row_style}">
                        <td>{ticker}</td>
                        <td class="{regime_class}">{current_regime}</td>
                        <td>{reference_index}</td>
                        <td class="{alignment_class}">{regime_alignment}</td>
                        <td>{volatility}</td>
                        <td>{trend_strength}</td>
                        <td>{hurst}</td>
                    </tr>
            """

    html_content += """
                </table>
            </div>

            <h2>Stop Loss Recommendations</h2>
            <div class="section">
                <p>Based on the market regime analysis, here are the recommended ATR multipliers for stop loss calculations:</p>
                <table>
                    <tr>
                        <th>Ticker</th>
                        <th>Regime</th>
                        <th>ATR Multiplier (LONG)</th>
                        <th>ATR Multiplier (SHORT)</th>
                        <th>Explanation</th>
                    </tr>
    """

    # Add stop loss recommendations
    all_tickers = small_cap_stocks + mid_cap_stocks + large_cap_stocks
    for ticker in sorted(all_tickers):
        data = all_ticker_data[ticker]
        if data['periods'] is not None and not data['periods'].empty:
            current_regime = data['periods'].sort_values('end_date', ascending=False).iloc[0]['regime']

            # Determine ATR multipliers based on regime
            if current_regime == "TRENDING_BULLISH":
                long_multiplier = 2.0
                short_multiplier = 1.5
                explanation = "Wider stops for LONG positions, tighter for SHORT positions in bullish trend"
            elif current_regime == "TRENDING_BEARISH":
                long_multiplier = 1.5
                short_multiplier = 2.0
                explanation = "Tighter stops for LONG positions, wider for SHORT positions in bearish trend"
            elif current_regime == "RANGING_LOW_VOL":
                long_multiplier = 1.5
                short_multiplier = 1.5
                explanation = "Moderate stops for all positions in low volatility range"
            elif current_regime == "RANGING_HIGH_VOL":
                long_multiplier = 2.5
                short_multiplier = 2.5
                explanation = "Wide stops for all positions due to high volatility"
            else:  # Transitioning or Unknown
                long_multiplier = 2.0
                short_multiplier = 2.0
                explanation = "Moderately wide stops for all positions in transitioning market"

            # Convert regime to CSS class
            regime_class = current_regime.lower().replace('_', '-') if current_regime else 'unknown'

            html_content += f"""
                    <tr>
                        <td>{ticker}</td>
                        <td class="{regime_class}">{current_regime}</td>
                        <td>{long_multiplier:.1f}x</td>
                        <td>{short_multiplier:.1f}x</td>
                        <td>{explanation}</td>
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

if __name__ == "__main__":
    all_ticker_data = analyze_index_and_stocks()
    generate_html_report(all_ticker_data, "SMALLCAP", "MIDCAP", "TOP100CASE")