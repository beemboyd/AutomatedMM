#!/usr/bin/env python3
"""
Accumulation/Distribution Phase Analyzer

This module analyzes price and volume patterns to identify if a stock is in an
accumulation phase or distribution phase based on price-volume relationships.

Accumulation vs Distribution Rules:
1. Accumulation: Price increases with a volume spike
2. Distribution: Price decreases with a volume spike
3. Distribution: Price increases with low volume
4. Accumulation: Price decreases with low volume
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import logging
from enum import Enum

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MarketPhaseType(Enum):
    """Market phase type enumeration for accumulation/distribution patterns"""
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class AccumulationDistributionAnalyzer:
    """
    Analyzes price and volume patterns to identify accumulation and distribution phases.
    """
    
    def __init__(self, volume_spike_threshold=1.5, low_volume_threshold=0.7, price_change_threshold=0.002,
                 lookback_periods=10, strength_lookback=30, sensitivity='medium'):
        """
        Initialize the analyzer with thresholds for pattern detection.
        
        Args:
            volume_spike_threshold (float): Threshold for volume spike detection (multiple of average volume)
            low_volume_threshold (float): Threshold for low volume detection (multiple of average volume)
            price_change_threshold (float): Minimum price change to consider as significant
            lookback_periods (int): Number of periods to look back for calculating average volume
        """
        self.volume_spike_threshold = volume_spike_threshold
        self.low_volume_threshold = low_volume_threshold
        self.price_change_threshold = price_change_threshold
        self.lookback_periods = lookback_periods
        self.strength_lookback = strength_lookback

        # Adjust thresholds based on sensitivity setting
        if sensitivity == 'high':
            self.volume_spike_threshold = 1.3
            self.low_volume_threshold = 0.8
            self.price_change_threshold = 0.001
        elif sensitivity == 'low':
            self.volume_spike_threshold = 2.0
            self.low_volume_threshold = 0.5
            self.price_change_threshold = 0.004
    
    def analyze(self, data):
        """
        Analyze price and volume patterns for accumulation and distribution phases.
        
        Args:
            data (pd.DataFrame): DataFrame with OHLCV data
                Required columns: 'Open', 'High', 'Low', 'Close', 'Volume', and 'DateTime'
                
        Returns:
            pd.DataFrame: Original data with additional columns for phase analysis
        """
        # Verify required columns
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in required_cols:
            if col not in data.columns:
                raise ValueError(f"Required column {col} not found in data")
        
        # Make a copy to avoid modifying the original dataframe
        result = data.copy()
        
        # Calculate price changes
        result['PriceChange'] = result['Close'].pct_change()
        result['PriceChangeAbs'] = result['PriceChange'].abs()
        
        # Calculate rolling average volume
        result['AvgVolume'] = result['Volume'].rolling(window=self.lookback_periods).mean().shift(1)
        
        # Calculate volume ratio compared to average
        result['VolumeRatio'] = result['Volume'] / result['AvgVolume']
        
        # Initialize phase column
        result['Phase'] = MarketPhaseType.NEUTRAL.value
        
        # Identify volume spikes and low volume
        result['VolumeSpikeFlag'] = result['VolumeRatio'] > self.volume_spike_threshold
        result['LowVolumeFlag'] = result['VolumeRatio'] < self.low_volume_threshold
        
        # Identify significant price changes
        result['SignificantPriceChangeFlag'] = result['PriceChangeAbs'] > self.price_change_threshold
        
        # Implement the four rules for accumulation/distribution
        # 1. Accumulation: Price increases with a volume spike (smart money buying)
        # 2. Distribution: Price decreases with a volume spike (smart money selling)
        # 3. Distribution: Price increases with low volume (lack of buying conviction)
        # 4. Accumulation: Price decreases with low volume (lack of selling pressure)
        
        # Initialize arrays for efficiency
        phases = np.array([MarketPhaseType.NEUTRAL.value] * len(result))
        signals = np.array([0] * len(result))
        
        for i in range(len(result)):
            if pd.isna(result.iloc[i]['VolumeRatio']) or pd.isna(result.iloc[i]['PriceChange']):
                phases[i] = MarketPhaseType.UNKNOWN.value
                continue
                
            price_change = result.iloc[i]['PriceChange']
            volume_spike = result.iloc[i]['VolumeSpikeFlag']
            low_volume = result.iloc[i]['LowVolumeFlag']
            significant_price_change = result.iloc[i]['SignificantPriceChangeFlag']
            
            # Only apply rules if price change is significant
            if significant_price_change:
                if price_change > 0 and volume_spike:
                    # Rule 1: Accumulation (Price up, Volume spike)
                    phases[i] = MarketPhaseType.ACCUMULATION.value
                    signals[i] = 1
                elif price_change < 0 and volume_spike:
                    # Rule 2: Distribution (Price down, Volume spike)
                    phases[i] = MarketPhaseType.DISTRIBUTION.value
                    signals[i] = -1
                elif price_change > 0 and low_volume:
                    # Rule 3: Distribution (Price up, Low volume)
                    phases[i] = MarketPhaseType.DISTRIBUTION.value
                    signals[i] = -1
                elif price_change < 0 and low_volume:
                    # Rule 4: Accumulation (Price down, Low volume)
                    phases[i] = MarketPhaseType.ACCUMULATION.value
                    signals[i] = 1
        
        # Add columns to result dataframe
        result['Phase'] = phases
        result['Signal'] = signals
        
        # Calculate strength of the phase by combining signal and volume ratio
        result['PhaseStrength'] = result['Signal'] * result['VolumeRatio']
        
        # Calculate cumulative strength over the period
        result['CumPhaseStrength'] = result['PhaseStrength'].cumsum()
        
        return result
    
    def get_phase_summary(self, data, lookback_periods=None):
        """
        Get a summary of the latest market phase based on recent data.
        
        Args:
            data (pd.DataFrame): Analyzed data with phase information
            lookback_periods (int): Number of recent periods to consider
            
        Returns:
            dict: Summary information about the current market phase
        """
        if lookback_periods is None:
            lookback_periods = self.strength_lookback

        if len(data) < lookback_periods:
            lookback_periods = len(data)

        recent_data = data.iloc[-lookback_periods:]

        # Get even more recent data for short-term trend (last 1/3 of lookback period)
        short_term_periods = max(int(lookback_periods / 3), 5)
        short_term_data = data.iloc[-short_term_periods:]
        
        # Count phases
        phase_counts = recent_data['Phase'].value_counts()
        
        # Calculate average strength
        accumulation_strength = recent_data[recent_data['Phase'] == MarketPhaseType.ACCUMULATION.value]['PhaseStrength'].mean()
        distribution_strength = recent_data[recent_data['Phase'] == MarketPhaseType.DISTRIBUTION.value]['PhaseStrength'].mean()
        
        if pd.isna(accumulation_strength):
            accumulation_strength = 0
        if pd.isna(distribution_strength):
            distribution_strength = 0
            
        # Calculate net phase strength
        net_strength = recent_data['PhaseStrength'].sum()

        # Calculate short-term trend strength
        short_term_strength = short_term_data['PhaseStrength'].sum()

        # Calculate volume trend
        volume_trend = recent_data['Volume'].pct_change(5).mean() * 100

        # Calculate price trend
        price_trend = recent_data['Close'].pct_change(5).mean() * 100
        
        # Calculate streak (consecutive same phases)
        current_phase = recent_data.iloc[-1]['Phase']
        current_streak = 0
        for i in range(len(recent_data)-1, -1, -1):
            if recent_data.iloc[i]['Phase'] == current_phase:
                current_streak += 1
            else:
                break
        
        # Determine dominant phase
        accumulation_count = phase_counts.get(MarketPhaseType.ACCUMULATION.value, 0)
        distribution_count = phase_counts.get(MarketPhaseType.DISTRIBUTION.value, 0)
        
        if accumulation_count > distribution_count:
            dominant_phase = MarketPhaseType.ACCUMULATION.value
            dominant_percentage = accumulation_count / lookback_periods * 100
        elif distribution_count > accumulation_count:
            dominant_phase = MarketPhaseType.DISTRIBUTION.value
            dominant_percentage = distribution_count / lookback_periods * 100
        else:
            dominant_phase = MarketPhaseType.NEUTRAL.value
            dominant_percentage = 0
            
        # Calculate divergence between price and volume
        price_vol_correlation = recent_data['PriceChange'].corr(recent_data['VolumeRatio'])

        # Identify potential reversals
        potential_reversal = (short_term_strength < 0 and net_strength > 0) or (short_term_strength > 0 and net_strength < 0)

        # Identify pattern strength as strong, moderate or weak
        pattern_strength = "strong"
        if abs(net_strength) < 5:
            pattern_strength = "weak"
        elif abs(net_strength) < 15:
            pattern_strength = "moderate"

        # Calculate overall conviction level
        if pattern_strength == "strong" and current_streak >= 3:
            conviction = "high"
        elif pattern_strength == "weak" or current_streak <= 1:
            conviction = "low"
        else:
            conviction = "medium"

        summary = {
            'current_phase': current_phase,
            'current_streak': current_streak,
            'dominant_phase': dominant_phase,
            'dominant_percentage': dominant_percentage,
            'accumulation_count': accumulation_count,
            'distribution_count': distribution_count,
            'neutral_count': phase_counts.get(MarketPhaseType.NEUTRAL.value, 0),
            'accumulation_strength': accumulation_strength,
            'distribution_strength': distribution_strength,
            'net_strength': net_strength,
            'short_term_strength': short_term_strength,
            'volume_trend': volume_trend,
            'price_trend': price_trend,
            'price_vol_correlation': price_vol_correlation,
            'potential_reversal': potential_reversal,
            'pattern_strength': pattern_strength,
            'conviction': conviction,
            'recent_trend': "ACCUMULATION" if net_strength > 0 else "DISTRIBUTION" if net_strength < 0 else "NEUTRAL",
            'short_term_trend': "ACCUMULATION" if short_term_strength > 0 else "DISTRIBUTION" if short_term_strength < 0 else "NEUTRAL"
        }
        
        return summary

    def plot_analysis(self, data, ticker, output_dir=None, timeframe="5min"):
        """
        Create a visualization of the accumulation/distribution analysis.

        Args:
            data (pd.DataFrame): Analyzed data
            ticker (str): Ticker symbol
            output_dir (str): Directory to save plot (if None, will show plot)
            timeframe (str): Timeframe of the data (e.g., "5min", "hourly", "daily")

        Returns:
            str: Path to saved plot if output_dir provided, else None
        """
        plt.figure(figsize=(14, 10))
        
        # Set up subplots
        price_ax = plt.subplot(3, 1, 1)
        volume_ax = plt.subplot(3, 1, 2, sharex=price_ax)
        strength_ax = plt.subplot(3, 1, 3, sharex=price_ax)
        
        # Plot price
        price_ax.plot(data.index, data['Close'], label='Close Price', color='black')
        price_ax.set_title(f"{ticker} - Price-Volume Analysis for Accumulation/Distribution")
        price_ax.set_ylabel('Price')
        price_ax.grid(True)
        
        # Highlight accumulation and distribution phases on price chart
        accumulation_idx = data[data['Phase'] == MarketPhaseType.ACCUMULATION.value].index
        distribution_idx = data[data['Phase'] == MarketPhaseType.DISTRIBUTION.value].index
        
        price_ax.scatter(accumulation_idx, data.loc[accumulation_idx, 'Close'], 
                      color='green', marker='^', s=50, label='Accumulation')
        price_ax.scatter(distribution_idx, data.loc[distribution_idx, 'Close'], 
                      color='red', marker='v', s=50, label='Distribution')
        price_ax.legend()
        
        # Plot volume
        volume_ax.bar(data.index, data['Volume'], color='blue', alpha=0.5, label='Volume')
        volume_ax.set_ylabel('Volume')
        volume_ax.grid(True)
        
        # Plot volume spikes and low volume
        volume_spike_idx = data[data['VolumeSpikeFlag']].index
        low_volume_idx = data[data['LowVolumeFlag']].index
        
        volume_ax.scatter(volume_spike_idx, data.loc[volume_spike_idx, 'Volume'], 
                        color='orange', marker='*', s=80, label='Volume Spike')
        volume_ax.scatter(low_volume_idx, data.loc[low_volume_idx, 'Volume'], 
                        color='purple', marker='o', s=40, label='Low Volume')
        volume_ax.legend()
        
        # Plot phase strength
        strength_ax.bar(data.index, data['PhaseStrength'], 
                       color=data['PhaseStrength'].apply(lambda x: 'green' if x > 0 else 'red' if x < 0 else 'gray'), 
                       label='Phase Strength')
        strength_ax.plot(data.index, data['CumPhaseStrength'], color='blue', label='Cumulative Strength')
        strength_ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        strength_ax.set_ylabel('Strength')
        strength_ax.set_xlabel('Time')
        strength_ax.grid(True)
        strength_ax.legend()
        
        plt.tight_layout()
        
        # Get phase summary for plot title
        summary = self.get_phase_summary(data)
        
        # Add summary text
        summary_text = (
            f"Current Phase: {summary['current_phase'].upper()} (Streak: {summary['current_streak']})\n"
            f"Dominant Phase: {summary['dominant_phase'].upper()} ({summary['dominant_percentage']:.1f}%)\n"
            f"Recent Trend: {summary['recent_trend']} (Net Strength: {summary['net_strength']:.2f})"
        )
        plt.figtext(0.5, 0.01, summary_text, ha='center', fontsize=12, bbox=dict(facecolor='white', alpha=0.8))
        
        # Save or show plot
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            plot_path = os.path.join(output_dir, f"{ticker}_{timeframe}_accum_dist_analysis_{timestamp}.png")
            plt.savefig(plot_path)
            plt.close()
            return plot_path
        else:
            plt.show()
            return None


def load_time_frame_data(ticker, days=5, timeframe="5min"):
    """
    Load 5-minute data for a given ticker.
    
    In a real implementation, this would fetch data from a data provider.
    This is a placeholder that should be replaced with actual data loading logic.
    
    Args:
        ticker (str): Ticker symbol
        days (int): Number of days of data to load
        
    Returns:
        pd.DataFrame: DataFrame with OHLCV data
    """
    try:
        # Look for data in standard locations
        # First, check ML/data/ohlc_data directory
        folder_map = {
            "5min": "5min",
            "hourly": "hour",
            "daily": "daily"
        }

        suffixes = []
        if timeframe == "5min":
            suffixes = ["_5minute.csv", "_5min.csv", "_5m.csv", "_intraday.csv"]
        elif timeframe == "hourly":
            suffixes = ["_60minute.csv", "_hour.csv", "_1H.csv", "_1h.csv", "_hourly.csv"]
        elif timeframe == "daily":
            suffixes = ["_day.csv", "_1D.csv", "_1d.csv", "_daily.csv"]

        # First look in ML/data/ohlc_data directory
        file_paths = []
        folder = folder_map.get(timeframe, "daily")
        for suffix in suffixes:
            file_paths.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'data', 'ohlc_data', folder, f'{ticker}{suffix}'))

        # Then try the old BT/data location as fallback
        for suffix in suffixes:
            file_paths.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                         'BT', 'data', f'{ticker}{suffix}'))
        
        for file_path in file_paths:
            if os.path.exists(file_path):
                data = pd.read_csv(file_path)
                logger.info(f"Loaded data from {file_path}")
                
                # Standardize column names
                if 'datetime' in data.columns:
                    data.rename(columns={'datetime': 'DateTime'}, inplace=True)
                elif 'date' in data.columns:
                    data.rename(columns={'date': 'DateTime'}, inplace=True)
                    
                if 'open' in data.columns:
                    data.rename(columns={
                        'open': 'Open',
                        'high': 'High',
                        'low': 'Low',
                        'close': 'Close',
                        'volume': 'Volume'
                    }, inplace=True)
                
                # Convert datetime column to datetime type (handling timezone-aware datetimes)
                try:
                    # First convert to datetime
                    data['DateTime'] = pd.to_datetime(data['DateTime'])

                    # Handle timezone-aware datetimes by converting to timezone-naive
                    if data['DateTime'].dt.tz is not None:
                        data['DateTime'] = data['DateTime'].dt.tz_localize(None)
                except Exception as e:
                    logger.warning(f"Error converting datetime: {e}. Trying alternative approach.")
                    # Alternative approach: force conversion to string first
                    data['DateTime'] = pd.to_datetime(data['DateTime'].astype(str))

                # Filter for only the last 'days' days/hours/intervals based on timeframe
                # For hourly and daily timeframes, extend the lookback to get more data
                if timeframe == "5min":
                    cutoff_days = days
                elif timeframe == "hourly":
                    cutoff_days = days * 3  # More days for hourly data
                elif timeframe == "daily":
                    cutoff_days = days * 10  # Much more days for daily data
                else:
                    cutoff_days = days

                cutoff_date = datetime.now() - timedelta(days=cutoff_days)

                # Ensure cutoff_date is timezone-naive for comparison
                if hasattr(cutoff_date, 'tzinfo') and cutoff_date.tzinfo is not None:
                    cutoff_date = cutoff_date.replace(tzinfo=None)

                # Filter data using safe comparison
                data = data[data['DateTime'] >= cutoff_date]
                
                # Set DateTime as index
                data.set_index('DateTime', inplace=True)
                
                # Sort by datetime to ensure chronological order
                data.sort_index(inplace=True)
                
                return data
        
        # If we can't find a file, generate mock data
        logger.warning(f"No data file found for {ticker}, generating mock data")
        return generate_mock_data(ticker, days, timeframe)
    
    except Exception as e:
        logger.error(f"Error loading data for {ticker}: {e}")
        return generate_mock_data(ticker, days, timeframe)


def generate_mock_data(ticker, days=5, timeframe="5min"):
    """
    Generate mock OHLCV data for testing when real data is not available.
    
    Args:
        ticker (str): Ticker symbol
        days (int): Number of days to generate
        
    Returns:
        pd.DataFrame: DataFrame with mock OHLCV data
    """
    # Calculate number of intervals in the trading day based on timeframe
    if timeframe == "5min":
        intervals_per_day = int(6.5 * 60 // 5)  # 5-minute intervals (assume 6.5 hour trading day)
    elif timeframe == "hourly":
        intervals_per_day = int(6.5)  # hourly intervals
    elif timeframe == "daily":
        intervals_per_day = 1  # daily intervals
    else:
        intervals_per_day = int(6.5 * 60 // 5)  # default to 5-minute
    
    # Calculate total number of intervals
    total_intervals = intervals_per_day * days
    
    # Generate dates
    end_date = datetime.now().replace(hour=15, minute=30, second=0, microsecond=0)
    dates = [end_date - timedelta(minutes=5*i) for i in range(total_intervals)]
    dates.reverse()  # Put in chronological order
    
    # Generate mock price data
    start_price = 100
    prices = [start_price]
    for i in range(1, total_intervals):
        # Simulate price with some random walk
        price_change = np.random.normal(0, 0.002) * prices[-1]
        prices.append(prices[-1] + price_change)
    
    # Generate open, high, low, close from prices
    opens = prices.copy()
    closes = []
    highs = []
    lows = []
    
    for i in range(len(prices)):
        # For the close price, add a small random adjustment
        close_adj = prices[i] * (1 + np.random.normal(0, 0.001))
        closes.append(close_adj)
        
        # High and low are based on the higher/lower of open and close, plus some random adjustment
        base_high = max(opens[i], close_adj)
        base_low = min(opens[i], close_adj)
        
        high_adj = base_high * (1 + abs(np.random.normal(0, 0.002)))
        low_adj = base_low * (1 - abs(np.random.normal(0, 0.002)))
        
        highs.append(high_adj)
        lows.append(low_adj)
    
    # Generate volumes with some spikes and low volume periods
    base_volume = 100000
    volumes = []
    
    for i in range(total_intervals):
        # Base volume with noise
        vol = base_volume * (1 + np.random.normal(0, 0.3))
        
        # Add occasional volume spikes (5% chance)
        if np.random.random() < 0.05:
            vol *= np.random.uniform(1.5, 3.0)
        
        # Add occasional low volume (10% chance)
        if np.random.random() < 0.1:
            vol *= np.random.uniform(0.3, 0.7)
        
        volumes.append(max(int(vol), 100))  # Ensure minimum volume of 100
    
    # Create DataFrame
    data = pd.DataFrame({
        'Open': opens,
        'High': highs,
        'Low': lows,
        'Close': closes,
        'Volume': volumes
    }, index=dates)
    
    return data


def analyze_ticker(ticker, days=20, output_dir=None, sensitivity='medium', strength_lookback=10, timeframe="5min"):
    """
    Analyze a ticker for accumulation/distribution patterns.
    
    Args:
        ticker (str): Ticker symbol
        days (int): Number of days of data to analyze
        output_dir (str): Directory to save output
        
    Returns:
        dict: Analysis results
    """
    logger.info(f"Analyzing {ticker} for accumulation/distribution patterns")
    
    # Load data
    data = load_time_frame_data(ticker, days, timeframe)
    
    # Set the minimum data points required based on timeframe
    if timeframe == "5min":
        min_data_points = 20
    elif timeframe == "hourly":
        min_data_points = 7  # At least 7 hours
    elif timeframe == "daily":
        min_data_points = 5  # At least 5 days
    else:
        min_data_points = 10

    if data is None or len(data) < min_data_points:
        logger.error(f"Insufficient data for {ticker}: found {len(data) if data is not None else 0} points, need {min_data_points}")
        return None
    
    # Create analyzer with specified parameters
    analyzer = AccumulationDistributionAnalyzer(strength_lookback=strength_lookback, sensitivity=sensitivity)
    
    # Analyze data
    analyzed_data = analyzer.analyze(data)
    
    # Get phase summary
    summary = analyzer.get_phase_summary(analyzed_data)
    
    # Create visualization
    if output_dir is None:
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'results'
        )
    
    plot_path = analyzer.plot_analysis(analyzed_data, ticker, output_dir, timeframe)
    
    # Package results
    results = {
        'ticker': ticker,
        'data': analyzed_data,
        'summary': summary,
        'plot_path': plot_path,
        'analyzer': analyzer
    }
    
    logger.info(f"Analysis complete for {ticker}")
    logger.info(f"Current phase: {summary['current_phase']}")
    logger.info(f"Dominant phase: {summary['dominant_phase']} ({summary['dominant_percentage']:.1f}%)")
    logger.info(f"Recent trend: {summary['recent_trend']} (Net strength: {summary['net_strength']:.2f})")
    
    return results


def print_analysis_summary(results, detailed=True, timeframe="5min"):
    """
    Print a human-readable summary of the analysis results.
    
    Args:
        results (dict): Analysis results
    """
    if not results:
        print("No analysis results available")
        return
    
    ticker = results['ticker']
    summary = results['summary']
    
    print(f"\n{'='*80}")
    print(f"ACCUMULATION/DISTRIBUTION ANALYSIS FOR {ticker} ({timeframe.upper()})")
    print(f"{'='*80}")
    
    print(f"\nCURRENT MARKET PHASE: {summary['current_phase'].upper()}")
    print(f"Consecutive periods in this phase: {summary['current_streak']}")

    lookback = results['analyzer'].strength_lookback
    print(f"\nDOMINANT PHASE (LAST {lookback} PERIODS): {summary['dominant_phase'].upper()} ({summary['dominant_percentage']:.1f}%)")
    print(f"Accumulation periods: {summary['accumulation_count']}")
    print(f"Distribution periods: {summary['distribution_count']}")
    print(f"Neutral periods: {summary['neutral_count']}")

    print(f"\nPHASE STRENGTH METRICS:")
    print(f"Accumulation strength: {summary['accumulation_strength']:.2f}")
    print(f"Distribution strength: {summary['distribution_strength']:.2f}")
    print(f"Net strength: {summary['net_strength']:.2f}")

    print(f"\nRECENT MARKET TREND: {summary['recent_trend']} ({summary['pattern_strength'].upper()})")

    if detailed:
        print(f"\nADDITIONAL ANALYSIS METRICS:")
        print(f"Short-term trend: {summary['short_term_trend']}")
        print(f"Price trend: {summary['price_trend']:.2f}%")
        print(f"Volume trend: {summary['volume_trend']:.2f}%")
        print(f"Price-volume correlation: {summary['price_vol_correlation']:.2f}")
        print(f"Overall conviction: {summary['conviction'].upper()}")

        if summary['potential_reversal']:
            print(f"\n⚠️ POTENTIAL TREND REVERSAL DETECTED")
            print(f"  Long-term trend: {summary['recent_trend']}")
            print(f"  Short-term trend: {summary['short_term_trend']}")
    
    # Add trading strategy implications based on the analysis
    print(f"\n{'-'*80}")
    print("TRADING STRATEGY IMPLICATIONS")
    print(f"{'-'*80}")
    
    if summary['recent_trend'] == "ACCUMULATION":
        print("\nThe market shows signs of ACCUMULATION. This suggests:")
        print("  • Institutional buying interest is present")
        print("  • Higher probability of upward price movement")
        print("  • Consider LONG positions with appropriate stop losses")
        print("  • Look for continuation patterns and breakouts")
        
        if summary['current_phase'] == MarketPhaseType.DISTRIBUTION.value:
            print("\nCAUTION: While the overall trend shows accumulation, the current phase")
            print("         indicates distribution. This could signal a short-term reversal.")
            
    elif summary['recent_trend'] == "DISTRIBUTION":
        print("\nThe market shows signs of DISTRIBUTION. This suggests:")
        print("  • Institutional selling pressure is present")
        print("  • Higher probability of downward price movement")
        print("  • Consider SHORT positions with appropriate stop losses")
        print("  • Be cautious with new LONG positions")
        print("  • Look for failure patterns and breakdowns")
        
        if summary['current_phase'] == MarketPhaseType.ACCUMULATION.value:
            print("\nNOTE: While the overall trend shows distribution, the current phase")
            print("      indicates accumulation. This could signal a potential reversal.")
    
    else:  # NEUTRAL
        print("\nThe market appears NEUTRAL. This suggests:")
        print("  • No clear institutional bias detected")
        print("  • Price may continue in a sideways pattern")
        print("  • Consider reducing position sizes and shorter-term trades")
        print("  • Look for range-bound trading opportunities")
        print("  • Wait for clearer signals before taking larger positions")
    
    # Additional notes based on strength
    if abs(summary['net_strength']) < 5:
        print("\nWEAK SIGNAL: The strength of the current trend is relatively weak.")
        print("             Consider waiting for stronger confirmation before trading.")
    elif abs(summary['net_strength']) > 15:
        print("\nSTRONG SIGNAL: The strength of the current trend is significant.")
        print("               This suggests a higher probability the trend will continue.")
    
    print(f"\n{'='*80}")
    print(f"Analysis generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}")


if __name__ == "__main__":
    # Check if command line arguments are provided
    import argparse
    import sys

    # Define parser for command-line usage
    parser = argparse.ArgumentParser(description='Analyze stock for accumulation/distribution patterns')
    parser.add_argument('--ticker', type=str, help='Ticker symbol to analyze')
    parser.add_argument('--days', type=int, default=5, help='Number of days of data to analyze')
    parser.add_argument('--output-dir', type=str, help='Directory to save output')
    parser.add_argument('--timeframe', type=str, default="daily", choices=["5min", "hourly", "daily"],
                        help='Timeframe for analysis (5min, hourly, or daily)')

    args = parser.parse_args()

    # If ticker is not provided via command line, ask for it interactively
    ticker = args.ticker
    if not ticker:
        ticker = input("Enter ticker symbol to analyze: ").strip().upper()

    # Ask for timeframe if not specified
    timeframe = args.timeframe
    if not args.timeframe and "--timeframe" not in sys.argv:
        print("\nSelect timeframe for analysis:")
        print("1. Daily (default)")
        print("2. Hourly")
        print("3. 5-minute")
        timeframe_choice = input("Enter your choice (1-3): ").strip()

        if timeframe_choice == "2":
            timeframe = "hourly"
        elif timeframe_choice == "3":
            timeframe = "5min"
        else:
            timeframe = "daily"

    # Ask for days if not specified
    days = args.days
    if not args.days and "--days" not in sys.argv:
        try:
            days_input = input(f"\nNumber of days of data to analyze (default: {days}): ").strip()
            if days_input:
                days = int(days_input)
        except ValueError:
            print(f"Invalid input. Using default: {days} days")

    print(f"\nAnalyzing {ticker} using {timeframe} data for the past {days} days...")

    # Run analysis
    results = analyze_ticker(ticker, days, args.output_dir, timeframe=timeframe)

    # Print summary
    if results:
        print_analysis_summary(results, timeframe=timeframe)
        print(f"\nPlot saved to: {results['plot_path']}")
    else:
        print(f"Analysis failed for {ticker}")