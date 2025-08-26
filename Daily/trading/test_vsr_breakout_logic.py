#!/usr/bin/env python3
"""
Test VSR Breakout Logic
Tests the 4-candle lookback breakout confirmation logic
"""

import os
import sys
import datetime
import json
import requests

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from user_context_manager import (
    get_context_manager,
    get_user_data_handler,
    UserCredentials
)

def fetch_vsr_tickers_from_api():
    """Fetch VSR tickers from dashboard API"""
    try:
        response = requests.get("http://localhost:3001/api/trending-tickers", timeout=5)
        if response.status_code == 200:
            data = response.json()
            all_tickers = []
            categories = data.get('categories', {})
            
            for ticker_data in categories.get('all_tickers', []):
                ticker = ticker_data.get('ticker')
                score = ticker_data.get('score', 0)
                momentum = ticker_data.get('momentum', 0)
                
                # Filter for score >= 60 and momentum >= 2%
                if ticker and score >= 60 and momentum >= 2.0:
                    all_tickers.append({
                        'ticker': ticker,
                        'score': score,
                        'momentum': momentum,
                        'price': ticker_data.get('price', 0)
                    })
            
            return sorted(all_tickers, key=lambda x: (x['score'], x['momentum']), reverse=True)
    except Exception as e:
        print(f"Error fetching from API: {e}")
        return []

def analyze_breakout(ticker, data_handler):
    """Analyze if ticker has broken out above previous 4 hourly candle highs"""
    try:
        # Get hourly data for last 2 days
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=2)
        
        hourly_data = data_handler.fetch_historical_data(
            ticker,
            interval="60minute",
            from_date=start_date.strftime('%Y-%m-%d'),
            to_date=end_date.strftime('%Y-%m-%d')
        )
        
        if hourly_data is None or hourly_data.empty:
            return None
        
        # Remove current incomplete candle
        if len(hourly_data) > 1:
            completed_candles = hourly_data.iloc[:-1]
        else:
            return None
        
        # Get last 4 completed candles
        lookback = 4
        if len(completed_candles) < lookback:
            recent_candles = completed_candles
        else:
            recent_candles = completed_candles.iloc[-lookback:]
        
        # Find highest high from these candles (resistance level)
        highest_high = float(recent_candles['High'].max())
        
        # Get current price
        quote = data_handler.kite.quote([f"NSE:{ticker}"])
        if quote and f"NSE:{ticker}" in quote:
            current_price = float(quote[f"NSE:{ticker}"].get('last_price', 0))
        else:
            return None
        
        # Check if we've broken above resistance
        has_broken_out = current_price > highest_high
        
        return {
            'ticker': ticker,
            'current_price': current_price,
            'resistance_level': highest_high,
            'has_broken_out': has_broken_out,
            'breakout_percentage': ((current_price - highest_high) / highest_high * 100) if highest_high > 0 else 0,
            'candles_analyzed': len(recent_candles),
            'period': f"{recent_candles.index[0]} to {recent_candles.index[-1]}" if len(recent_candles) > 0 else "N/A",
            'buy_price': round(highest_high * 1.005, 2) if has_broken_out else None  # 0.5% above resistance
        }
        
    except Exception as e:
        print(f"Error analyzing {ticker}: {e}")
        return None

def main():
    """Test the breakout logic"""
    print("\n" + "="*80)
    print("VSR BREAKOUT LOGIC TEST - Clean Breakout Above Resistance")
    print("="*80)
    
    # Setup for Sai user (default for testing)
    context_manager = get_context_manager()
    credentials = UserCredentials(
        name="Sai",
        api_key="",  # Will be loaded from config
        api_secret="",
        access_token=""
    )
    
    # Load actual credentials from config
    import configparser
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    config.read(config_path)
    
    if config.has_section('API_CREDENTIALS_Sai'):
        credentials.api_key = config.get('API_CREDENTIALS_Sai', 'api_key')
        credentials.api_secret = config.get('API_CREDENTIALS_Sai', 'api_secret')
        credentials.access_token = config.get('API_CREDENTIALS_Sai', 'access_token')
    
    context_manager.set_current_user("Sai", credentials)
    data_handler = get_user_data_handler()
    
    # Fetch VSR tickers
    print("\nFetching VSR tickers from dashboard...")
    vsr_tickers = fetch_vsr_tickers_from_api()
    
    if not vsr_tickers:
        print("No VSR tickers found with score >= 60 and momentum >= 2%")
        return
    
    print(f"Found {len(vsr_tickers)} qualifying VSR tickers\n")
    
    # Analyze top 10 tickers
    print("BREAKOUT ANALYSIS (Top 10 VSR Tickers)")
    print("-"*80)
    print(f"{'Ticker':<10} {'Score':<7} {'Mom%':<8} {'Current':<10} {'Resistance':<10} {'Status':<15} {'Break%':<8} {'Buy Price':<10}")
    print("-"*80)
    
    breakout_candidates = []
    congestion_tickers = []
    
    for ticker_data in vsr_tickers[:10]:
        ticker = ticker_data['ticker']
        analysis = analyze_breakout(ticker, data_handler)
        
        if analysis:
            status = "✅ BREAKOUT" if analysis['has_broken_out'] else "⏸️ CONGESTION"
            
            print(f"{ticker:<10} {ticker_data['score']:<7} {ticker_data['momentum']:<8.2f} "
                  f"₹{analysis['current_price']:<10.2f} ₹{analysis['resistance_level']:<10.2f} "
                  f"{status:<15} {analysis['breakout_percentage']:<8.2f} "
                  f"{'₹' + str(analysis['buy_price']) if analysis['buy_price'] else 'N/A':<10}")
            
            if analysis['has_broken_out']:
                breakout_candidates.append(analysis)
            else:
                congestion_tickers.append(analysis)
    
    print("-"*80)
    
    # Summary
    print(f"\n📊 SUMMARY:")
    print(f"  • Clean Breakouts: {len(breakout_candidates)} tickers")
    print(f"  • In Congestion: {len(congestion_tickers)} tickers")
    
    if breakout_candidates:
        print(f"\n✅ READY TO TRADE (Clean breakouts above resistance):")
        for candidate in breakout_candidates:
            print(f"  • {candidate['ticker']}: Current ₹{candidate['current_price']:.2f} > "
                  f"Resistance ₹{candidate['resistance_level']:.2f} "
                  f"(+{candidate['breakout_percentage']:.2f}%) → Buy at ₹{candidate['buy_price']:.2f}")
    
    if congestion_tickers:
        print(f"\n⏸️ WAITING FOR BREAKOUT (Still in congestion):")
        for ticker in congestion_tickers[:5]:  # Show first 5
            gap = ticker['resistance_level'] - ticker['current_price']
            gap_pct = (gap / ticker['current_price'] * 100) if ticker['current_price'] > 0 else 0
            print(f"  • {ticker['ticker']}: Current ₹{ticker['current_price']:.2f} < "
                  f"Resistance ₹{ticker['resistance_level']:.2f} "
                  f"(needs +{gap_pct:.2f}% to breakout)")
    
    print("\n" + "="*80)
    print("LOGIC EXPLANATION:")
    print("1. Fetch VSR tickers with score >= 60 and momentum >= 2%")
    print("2. Analyze last 4 hourly candles to find resistance (highest high)")
    print("3. Check if current price has broken above resistance")
    print("4. Only place orders for clean breakouts (current > resistance)")
    print("5. Buy at 0.5% above resistance level for confirmed breakouts")
    print("="*80)

if __name__ == "__main__":
    main()