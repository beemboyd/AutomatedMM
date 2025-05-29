import numpy as np
import pandas as pd
import logging

from config import get_config

logger = logging.getLogger(__name__)

def calculate_indicators(data):
    """Calculate technical indicators using vectorized operations"""
    if data.empty:
        logger.warning("Cannot calculate indicators on empty data")
        return data
    
    # Check required columns
    if 'Close' not in data.columns:
        logger.error("'Close' column is missing from the data")
        return data
    
    # Check if there are enough data points - minimum reduced for backtesting
    if len(data) < 20:
        logger.warning(f"Insufficient data points. Only {len(data)} records available, minimum of 20 required.")
        return data
    
    config = get_config()
    
    # Get settings
    account_value = config.get_float('Trading', 'account_value', fallback=100000.0)
    volume_spike_threshold = config.get_float('Trading', 'volume_spike_threshold', fallback=4.0)
    gap_down_threshold = config.get_float('Trading', 'gap_down_threshold', fallback=-1.0)
    
    try:
        # Calculate EMA
        data['EMA_20'] = data['Close'].ewm(span=20, adjust=False).mean()
        
        # Calculate ATR components
        prev_close = data['Close'].shift(1)
        tr1 = data['High'] - data['Low']
        tr2 = (data['High'] - prev_close).abs()
        tr3 = (data['Low'] - prev_close).abs()
        data['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        data['ATR'] = data['TR'].rolling(window=20).mean().shift(1)
        
        # Calculate price gap
        data['price_gap'] = (data['Open'] - data['Close'].shift(1)) / data['Close'].shift(1) * 100
        data['MaxGap'] = data['price_gap'].rolling(window=100).max()
        data['GapPercent'] = data['price_gap']
        
        # Keltner Channel bands
        data['KC_upper'] = data['EMA_20'] + (2 * data['ATR'])
        data['KC_lower'] = data['EMA_20'] - (2 * data['ATR'])
        
        # Position Size, Stop Loss and Take Profit levels
        data['PosSize'] = account_value / data['Close']
        data['SL1'] = data['Close'] - (1.2 * data['ATR'])
        data['SL2'] = data['Close'] - (3 * data['ATR'])
        data['TP1'] = data['Close'] + 2 * data['ATR']
        
        # Slope calculation
        data['Slope'] = data['Close'].rolling(window=8).apply(
            lambda y: (np.polyfit(np.arange(len(y)), y, 1)[0] / y[-1]) * 100 if len(y) >= 8 and y[-1] != 0 else np.nan,
            raw=True
        )
        
        # Alpha as ratio of Slope to ATR
        data['Alpha'] = data['Slope'] / data['ATR']
        
        # Price and volume change
        data['price_change_pct'] = (data['Close'] - data['Close'].shift(1)) / data['Close'].shift(1)
        data['vol_change_pct'] = (data['Volume'] - data['Volume'].shift(1)) / data['Volume'].shift(1)
        data['C'] = data['price_change_pct'] * data['vol_change_pct']
        data.loc[data['vol_change_pct'] <= 0, 'C'] = 0
        
        logger.info(f"Calculated indicators for {len(data)} data points")
        return data
    
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        return data

def get_trade_signals(data, ticker):
    """Identify trading signals from calculated indicators"""
    config = get_config()
    volume_spike_threshold = config.get_float('Trading', 'volume_spike_threshold', fallback=4.0)
    gap_down_threshold = config.get_float('Trading', 'gap_down_threshold', fallback=-1.0)
    
    if len(data) < 4:
        logger.warning(f"Not enough data points for {ticker} to calculate signals")
        return None, None, 0, 0
    
    try:
        current_bar = data.iloc[-1]
        prev_bar = data.iloc[-2] if len(data) > 2 else None
        
        # Calculate volume spike average using previous 3 bars
        vol_spike_avg = data['vol_change_pct'].iloc[-4:-1].mean()
        
        # Check for gap down from previous day
        current_date = pd.to_datetime(current_bar['Date']).date()
        prev_day_data = data[pd.to_datetime(data['Date']).dt.date < current_date]
        
        gap_down_filtered = False
        if not prev_day_data.empty and len(data) > 1:
            prev_day_close = prev_day_data.iloc[-1]['Close']
            today_data = data[pd.to_datetime(data['Date']).dt.date == current_date]
            
            if not today_data.empty and 'Open' in today_data.columns and not today_data['Open'].isna().all():
                today_open = today_data.iloc[0]['Open']
                day_gap_percent = ((today_open - prev_day_close) / prev_day_close) * 100
                
                if day_gap_percent <= gap_down_threshold:
                    logger.info(f"Filtering out {ticker} due to gap down of {day_gap_percent:.2f}%")
                    gap_down_filtered = True
        
        # Basic conditions (without volume threshold)
        basic_long_condition = False
        basic_short_condition = False
        
        if prev_bar is not None:
            basic_long_condition = (
                (current_bar['Close'] > current_bar['KC_upper']) or
                (prev_bar['Close'] <= prev_bar['KC_upper'] and current_bar['Close'] > current_bar['KC_upper'])
            )
            
            basic_short_condition = (
                (current_bar['Close'] < current_bar['KC_lower']) or
                (prev_bar['Close'] >= prev_bar['KC_lower'] and current_bar['Close'] < current_bar['KC_lower'])
            )
        
        # For advances/declines counters
        advances = 1 if basic_long_condition and not gap_down_filtered else 0
        declines = 1 if basic_short_condition else 0
        
        # Long side condition with volume
        long_condition = False
        if prev_bar is not None:
            long_condition = (
                (current_bar['Close'] > current_bar['KC_upper'] and vol_spike_avg > volume_spike_threshold) or
                (prev_bar['Close'] <= prev_bar['KC_upper'] and current_bar['Close'] > current_bar['KC_upper'])
            )
        
        # Short side condition with volume
        short_condition = False
        if prev_bar is not None:
            short_condition = (
                (current_bar['Close'] < current_bar['KC_lower'] and vol_spike_avg > volume_spike_threshold) or
                (prev_bar['Close'] >= prev_bar['KC_lower'] and current_bar['Close'] < current_bar['KC_lower'])
            )
        
        # Return signals and counters
        long_signal = None
        short_signal = None
        
        if long_condition and not gap_down_filtered:
            try:
                long_signal = current_bar.copy()  # Make a copy to avoid any reference issues
                logger.info(f"{ticker} qualifies as LONG candidate")
                logger.debug(f"{ticker} LONG signal data: {list(long_signal.index)}")
            except Exception as e:
                logger.error(f"Error creating LONG signal for {ticker}: {e}")
                long_signal = None
        
        if short_condition:
            try:
                short_signal = current_bar.copy()  # Make a copy to avoid any reference issues
                logger.info(f"{ticker} qualifies as SHORT candidate")
                logger.debug(f"{ticker} SHORT signal data: {list(short_signal.index)}")
            except Exception as e:
                logger.error(f"Error creating SHORT signal for {ticker}: {e}")
                short_signal = None
        
        logger.debug(f"{ticker} returning signals - long: {'Yes' if long_signal is not None else 'No'}, short: {'Yes' if short_signal is not None else 'No'}")
        return long_signal, short_signal, advances, declines
    
    except Exception as e:
        logger.error(f"Error calculating trading signals for {ticker}: {e}")
        return None, None, 0, 0
