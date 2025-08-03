import os
import sys
import logging
import argparse
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ML.integration import get_dynamic_stop_loss
from ML.models.dynamic_stop_loss import PositionType
from data_handler import get_data_handler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def calculate_stops_for_ticker(ticker, position_type="LONG"):
    """
    Calculate and display dynamic stop loss values for a specific ticker.
    
    Args:
        ticker (str): Ticker symbol
        position_type (str): Position type ('LONG' or 'SHORT')
    """
    try:
        # Get data handler and dynamic stop loss module
        data_handler = get_data_handler()
        dynamic_sl = get_dynamic_stop_loss()
        
        # Get current price
        current_price = data_handler.fetch_current_price(ticker)
        if current_price is None:
            logger.error(f"Could not fetch current price for {ticker}")
            return
        
        # Calculate dynamic stop loss
        stop_loss = dynamic_sl.calculate_dynamic_stop_loss(ticker, position_type, current_price)
        
        if stop_loss is None:
            logger.error(f"Failed to calculate stop loss for {ticker}")
            return
        
        # Calculate stop loss distance
        if position_type.upper() == "LONG":
            distance = current_price - stop_loss
            distance_pct = (distance / current_price) * 100
        else:  # SHORT
            distance = stop_loss - current_price
            distance_pct = (distance / current_price) * 100
        
        # Display results
        print(f"\n{'-'*60}")
        print(f"DYNAMIC STOP LOSS CALCULATION FOR {ticker} ({position_type})")
        print(f"{'-'*60}")
        print(f"Current Price: ₹{current_price:.2f}")
        print(f"Stop Loss:     ₹{stop_loss:.2f}")
        print(f"Distance:      ₹{distance:.2f} ({distance_pct:.2f}%)")
        print(f"{'-'*60}")
        
        return {
            'ticker': ticker,
            'position_type': position_type,
            'current_price': current_price,
            'stop_loss': stop_loss,
            'distance': distance,
            'distance_pct': distance_pct
        }
    
    except Exception as e:
        logger.error(f"Error calculating stops for {ticker}: {str(e)}")
        return None

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Dynamic Stop Loss Example')
    
    parser.add_argument('--ticker', type=str, required=True,
                        help='Ticker symbol')
    parser.add_argument('--position-type', type=str, choices=['LONG', 'SHORT'], default='LONG',
                        help='Position type (LONG or SHORT)')
    
    return parser.parse_args()

def main():
    """Main function"""
    args = parse_arguments()
    
    # Calculate stops for the specified ticker
    result = calculate_stops_for_ticker(args.ticker, args.position_type)
    
    if result:
        logger.info(f"Successfully calculated stop loss for {args.ticker}")
    else:
        logger.error(f"Failed to calculate stop loss for {args.ticker}")

if __name__ == "__main__":
    main()