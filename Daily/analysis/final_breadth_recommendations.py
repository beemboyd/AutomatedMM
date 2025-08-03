#!/usr/bin/env python3
"""
Final SMA Breadth Recommendations for Long and Short Trading
"""

print("\n" + "="*80)
print("OPTIMAL SMA20 BREADTH CONDITIONS FOR TRADING")
print("="*80)

print("\n📉 SHORT REVERSAL STRATEGY:")
print("-" * 40)
print("  ✅ BEST: SMA20 breadth between 35-50%")
print("     - Success Rate: 80%")
print("     - Average PnL: +2.91%")
print("  ✅ GOOD: SMA20 breadth between 25-35%")
print("     - Success Rate: 66.7%")
print("     - Average PnL: +0.66%")
print("  ❌ AVOID: SMA20 breadth below 20%")
print("     - Oversold bounce risk")
print("     - Average PnL: -0.86%")
print("  ❌ AVOID: SMA20 breadth above 50%")
print("     - Bullish conditions unfavorable for shorts")

print("\n📈 LONG REVERSAL STRATEGY:")
print("-" * 40)
print("  ✅ BEST: SMA20 breadth between 55-70%")
print("     - Success Rate: 43-46%")
print("     - Average PnL: +0.29% to +0.47%")
print("  ⚠️  MODERATE: SMA20 breadth between 45-55%")
print("     - Mixed results, use with caution")
print("  ❌ AVOID: SMA20 breadth below 45%")
print("     - Poor success rates (19-22%)")
print("     - Negative average returns")
print("  ❌ AVOID: SMA20 breadth above 70%")
print("     - Potentially overbought conditions")

print("\n🎯 KEY INSIGHTS:")
print("-" * 40)
print("1. Shorts work best in moderately weak markets (35-50% breadth)")
print("2. Longs work best in moderately strong markets (55-70% breadth)")
print("3. Extreme breadth readings (<20% or >70%) should be avoided")
print("4. The 'sweet spot' differs significantly for longs vs shorts")

print("\n" + "="*80)