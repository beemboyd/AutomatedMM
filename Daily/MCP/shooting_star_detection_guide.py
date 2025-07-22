#!/usr/bin/env python3
"""
Guide for detecting shooting star patterns using multiple timeframes
to avoid false breakouts at KC upper limits
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def identify_shooting_star_characteristics():
    """
    Key characteristics of shooting star patterns that lead to losses
    """
    
    print("="*80)
    print("SHOOTING STAR PATTERN DETECTION - MULTI-TIMEFRAME APPROACH")
    print("="*80)
    
    # 1. Classic Shooting Star Characteristics
    print("\n1. CLASSIC SHOOTING STAR CHARACTERISTICS:")
    print("-" * 50)
    print("   - Small real body at the bottom of the price range")
    print("   - Long upper shadow (at least 2x the real body)")
    print("   - Little to no lower shadow")
    print("   - Occurs after an uptrend or at resistance")
    print("   - High volume on the formation")
    
    # 2. Multi-Timeframe Confirmation
    print("\n2. MULTI-TIMEFRAME CONFIRMATION STRATEGY:")
    print("-" * 50)
    print("\nA. 15-Minute Chart (Primary Entry Timeframe):")
    print("   - Look for shooting star forming at KC upper band")
    print("   - Volume spike > 2x average volume")
    print("   - RSI > 70 (overbought)")
    print("   - Price rejection from high")
    
    print("\nB. 5-Minute Chart (Fine-Tuning):")
    print("   - Multiple red candles after the spike")
    print("   - Decreasing volume on pullbacks")
    print("   - Lower highs forming")
    print("   - Break below the shooting star's real body")
    
    print("\nC. 1-Hour Chart (Context):")
    print("   - At major resistance level")
    print("   - Extended move from support")
    print("   - Divergence in momentum indicators")
    
    # 3. Volume Analysis
    print("\n3. VOLUME ANALYSIS FOR SHOOTING STARS:")
    print("-" * 50)
    print("   - Initial spike: High volume on the up move")
    print("   - Rejection: Even higher volume on the reversal")
    print("   - Follow-through: Decreasing volume on any bounces")
    
    # 4. Entry Avoidance Rules
    print("\n4. RULES TO AVOID FALSE BREAKOUTS:")
    print("-" * 50)
    print("   Rule 1: Wait for candle close before entering")
    print("   Rule 2: If 15-min candle has >60% upper shadow, skip entry")
    print("   Rule 3: Check 5-min chart for immediate rejection")
    print("   Rule 4: Avoid entries if 3 consecutive 5-min red candles")
    print("   Rule 5: Skip if volume on rejection > entry volume")
    
    # 5. Safe Entry Checklist
    print("\n5. SAFE ENTRY CHECKLIST:")
    print("-" * 50)
    print("   ✓ Price closes above KC upper band (not just wicks)")
    print("   ✓ Real body is at least 50% of the total candle range")
    print("   ✓ No long upper shadows on 15-min candle")
    print("   ✓ 5-min chart shows continuation, not reversal")
    print("   ✓ Volume remains consistent, not climactic")
    print("   ✓ RSI < 75 on 15-min timeframe")
    
    # 6. Example Analysis
    print("\n6. EXAMPLE ANALYSIS OF YOUR LOSSES:")
    print("-" * 50)
    print("\nCase 1: BEML (Loss: -7.45%)")
    print("   - Likely entered on volume spike at resistance")
    print("   - Shooting star formed on 15-min")
    print("   - Immediate reversal within first hour")
    
    print("\nCase 2: KNRCON (Same-day loss: -4.70%)")
    print("   - Classic intraday shooting star")
    print("   - Entry on spike, exit on same day")
    print("   - Volume exhaustion pattern")
    
    # 7. Practical Implementation
    print("\n7. PRACTICAL IMPLEMENTATION:")
    print("-" * 50)
    print("""
# Before entering any KC upper band breakout:

1. Check 15-minute candle formation:
   if upper_shadow > (0.6 * candle_range):
       SKIP_ENTRY
   
2. Verify on 5-minute chart:
   last_3_candles = get_last_3_candles_5min()
   if all(candle.close < candle.open for candle in last_3_candles):
       SKIP_ENTRY
   
3. Volume confirmation:
   if rejection_volume > breakout_volume:
       SKIP_ENTRY
   
4. Wait for confirmation:
   if not wait_for_next_15min_candle_to_close_above_high():
       SKIP_ENTRY
""")
    
    # 8. Alternative Entry Strategy
    print("\n8. ALTERNATIVE ENTRY STRATEGY:")
    print("-" * 50)
    print("   Instead of entering on the breakout candle:")
    print("   1. Wait for pullback to KC upper band")
    print("   2. Enter on the bounce with tight stop loss")
    print("   3. Ensure 5-min chart shows support")
    print("   4. Volume should be lower on pullback")
    
    print("\n" + "="*80)
    print("CONCLUSION: Avoid entries on candles with long upper shadows at KC bands")
    print("="*80)

def calculate_shooting_star_score(high, low, open_price, close_price, volume, avg_volume):
    """
    Calculate a score to identify potential shooting star patterns
    Higher score = Higher probability of reversal
    """
    
    # Calculate candle measurements
    candle_range = high - low
    real_body = abs(close_price - open_price)
    upper_shadow = high - max(open_price, close_price)
    lower_shadow = min(open_price, close_price) - low
    
    # Scoring system (0-100)
    score = 0
    
    # 1. Upper shadow ratio (0-30 points)
    if candle_range > 0:
        upper_shadow_ratio = upper_shadow / candle_range
        if upper_shadow_ratio > 0.6:
            score += 30
        elif upper_shadow_ratio > 0.5:
            score += 20
        elif upper_shadow_ratio > 0.4:
            score += 10
    
    # 2. Small real body (0-20 points)
    if candle_range > 0:
        body_ratio = real_body / candle_range
        if body_ratio < 0.2:
            score += 20
        elif body_ratio < 0.3:
            score += 10
    
    # 3. Minimal lower shadow (0-20 points)
    if candle_range > 0:
        lower_shadow_ratio = lower_shadow / candle_range
        if lower_shadow_ratio < 0.1:
            score += 20
        elif lower_shadow_ratio < 0.2:
            score += 10
    
    # 4. Volume spike (0-30 points)
    if avg_volume > 0:
        volume_ratio = volume / avg_volume
        if volume_ratio > 3:
            score += 30
        elif volume_ratio > 2:
            score += 20
        elif volume_ratio > 1.5:
            score += 10
    
    return score

if __name__ == "__main__":
    identify_shooting_star_characteristics()
    
    # Example calculation
    print("\n\nEXAMPLE SHOOTING STAR SCORE CALCULATION:")
    print("-" * 50)
    
    # Example candle data
    example_score = calculate_shooting_star_score(
        high=100,
        low=95,
        open_price=96,
        close_price=95.5,
        volume=1000000,
        avg_volume=300000
    )
    
    print(f"Candle: High=100, Low=95, Open=96, Close=95.5")
    print(f"Volume: 1M (avg: 300K)")
    print(f"Shooting Star Score: {example_score}/100")
    print(f"Risk Level: {'HIGH' if example_score > 70 else 'MEDIUM' if example_score > 50 else 'LOW'}")