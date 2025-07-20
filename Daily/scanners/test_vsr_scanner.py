#!/usr/bin/env python
"""Test script for VSR Momentum Scanner"""

import os
import sys
import pandas as pd

# Add parent directories to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Daily.scanners.VSR_Momentum_Scanner import (
    calculate_vsr_indicators,
    detect_vsr_momentum,
    process_ticker
)

def test_vsr_calculation():
    """Test VSR calculation with sample data"""
    # Create sample hourly data
    dates = pd.date_range(start='2025-07-01 09:00', periods=100, freq='H')
    
    sample_data = pd.DataFrame({
        'Date': dates,
        'Open': [100 + i * 0.1 for i in range(100)],
        'High': [101 + i * 0.1 for i in range(100)],
        'Low': [99 + i * 0.1 for i in range(100)],
        'Close': [100.5 + i * 0.1 for i in range(100)],
        'Volume': [10000 + i * 100 for i in range(100)],
        'Ticker': 'TEST'
    })
    
    print("Testing VSR calculation...")
    result = calculate_vsr_indicators(sample_data)
    
    if result is not None:
        print("✓ VSR calculation successful")
        print(f"  Sample VSR values: {result['VSR'].tail(5).values}")
        print(f"  Sample VSR Ratio: {result['VSR_Ratio'].tail(5).values}")
        
        # Test pattern detection
        pattern = detect_vsr_momentum(result)
        if pattern:
            print(f"✓ Pattern detected: {pattern['pattern']}")
            print(f"  Probability Score: {pattern['probability_score']:.1f}")
        else:
            print("  No pattern detected (expected with synthetic data)")
    else:
        print("✗ VSR calculation failed")
    
    return result is not None

def test_single_ticker():
    """Test processing a single ticker"""
    print("\nTesting single ticker processing...")
    
    # Test with a known ticker
    test_ticker = "RELIANCE"
    print(f"Processing {test_ticker}...")
    
    try:
        result = process_ticker(test_ticker)
        if result:
            print(f"✓ Successfully processed {test_ticker}")
            print(f"  Pattern: {result['Pattern']}")
            print(f"  VSR Ratio: {result['VSR_Ratio']:.2f}")
            print(f"  Probability Score: {result['Probability_Score']:.1f}")
        else:
            print(f"  No pattern found for {test_ticker} (normal behavior)")
        return True
    except Exception as e:
        print(f"✗ Error processing {test_ticker}: {e}")
        return False

def verify_output_structure():
    """Verify output directory structure"""
    print("\nVerifying output structure...")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    hourly_dir = os.path.join(script_dir, "Hourly")
    hourly_html_dir = os.path.join(os.path.dirname(script_dir), "Detailed_Analysis", "Hourly")
    
    dirs_to_check = [
        ("Hourly results directory", hourly_dir),
        ("Hourly HTML directory", hourly_html_dir)
    ]
    
    all_good = True
    for name, path in dirs_to_check:
        if os.path.exists(path):
            print(f"✓ {name}: {path}")
        else:
            print(f"✗ {name} missing: {path}")
            all_good = False
    
    return all_good

def main():
    """Run all tests"""
    print("="*50)
    print("VSR Momentum Scanner Test Suite")
    print("="*50)
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: VSR Calculation
    tests_total += 1
    if test_vsr_calculation():
        tests_passed += 1
    
    # Test 2: Output Structure
    tests_total += 1
    if verify_output_structure():
        tests_passed += 1
    
    # Test 3: Single Ticker Processing
    tests_total += 1
    if test_single_ticker():
        tests_passed += 1
    
    print("\n" + "="*50)
    print(f"Tests passed: {tests_passed}/{tests_total}")
    
    if tests_passed == tests_total:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())