#!/usr/bin/env python3
"""
JSON Safe Encoder for Market Regime System

This module provides utilities to safely encode Python objects to JSON,
handling special cases like Infinity, NaN, and other non-JSON-compliant values.
"""

import json
import math
from typing import Any, Dict, List, Union


class SafeJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles Infinity and NaN values safely."""
    
    def encode(self, o):
        """Override encode to handle special float values."""
        if isinstance(o, float):
            if math.isinf(o):
                return '"inf"' if o > 0 else '"-inf"'
            elif math.isnan(o):
                return 'null'
        return super().encode(o)
    
    def iterencode(self, o, _one_shot=False):
        """Override iterencode to handle special values in nested structures."""
        for chunk in super().iterencode(o, _one_shot):
            yield chunk


def safe_float(value: Any, default: float = 0.0, max_value: float = 999999.0) -> float:
    """
    Convert a value to a safe float for JSON serialization.
    
    Args:
        value: The value to convert
        default: Default value if conversion fails
        max_value: Maximum allowed value (to cap infinity)
    
    Returns:
        A JSON-safe float value
    """
    try:
        if value is None:
            return default
        
        # Handle string 'inf'
        if isinstance(value, str):
            if value.lower() in ['inf', 'infinity', '+inf']:
                return max_value
            elif value.lower() in ['-inf', '-infinity']:
                return -max_value
            elif value.lower() in ['nan', 'none']:
                return default
        
        # Convert to float
        f_value = float(value)
        
        # Handle special float values
        if math.isinf(f_value):
            return max_value if f_value > 0 else -max_value
        elif math.isnan(f_value):
            return default
        
        # Cap to max value
        if abs(f_value) > max_value:
            return max_value if f_value > 0 else -max_value
        
        return f_value
        
    except (TypeError, ValueError):
        return default


def safe_ratio(long_count: Union[int, float], short_count: Union[int, float], 
               max_ratio: float = 100.0) -> float:
    """
    Calculate a safe Long/Short ratio for JSON serialization.
    
    Args:
        long_count: Number of long patterns
        short_count: Number of short patterns
        max_ratio: Maximum ratio value to return when short_count is 0
    
    Returns:
        A JSON-safe ratio value
    """
    # Handle edge cases
    if long_count == 0 and short_count == 0:
        return 1.0  # Neutral
    
    if short_count == 0:
        # Instead of infinity, return a capped high value
        if long_count > 0:
            return max_ratio  # Strong bullish
        return 1.0
    
    if long_count == 0:
        # All shorts, return inverse
        return 1.0 / max_ratio  # Strong bearish
    
    # Normal calculation
    ratio = long_count / short_count
    
    # Cap the ratio
    if ratio > max_ratio:
        return max_ratio
    elif ratio < (1.0 / max_ratio):
        return 1.0 / max_ratio
    
    return ratio


def sanitize_for_json(data: Any) -> Any:
    """
    Recursively sanitize data structure for JSON serialization.
    
    Converts all Infinity, NaN, and other non-JSON values to safe alternatives.
    
    Args:
        data: The data structure to sanitize
    
    Returns:
        A JSON-safe version of the data
    """
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    
    elif isinstance(data, list):
        return [sanitize_for_json(item) for item in data]
    
    elif isinstance(data, float):
        if math.isinf(data):
            return 999999.0 if data > 0 else -999999.0
        elif math.isnan(data):
            return None
        return data
    
    elif isinstance(data, str):
        # Handle string representations of special values
        if data.lower() in ['inf', 'infinity', '+inf']:
            return 999999.0
        elif data.lower() in ['-inf', '-infinity']:
            return -999999.0
        elif data.lower() in ['nan']:
            return None
        return data
    
    else:
        return data


def safe_json_dumps(data: Any, **kwargs) -> str:
    """
    Safely dump data to JSON string, handling all special cases.
    
    Args:
        data: The data to serialize
        **kwargs: Additional arguments for json.dumps
    
    Returns:
        A valid JSON string
    """
    # First sanitize the data
    safe_data = sanitize_for_json(data)
    
    # Then dump with safe encoder
    return json.dumps(safe_data, cls=SafeJSONEncoder, **kwargs)


def safe_json_dump(data: Any, fp, **kwargs) -> None:
    """
    Safely dump data to JSON file, handling all special cases.
    
    Args:
        data: The data to serialize
        fp: File pointer to write to
        **kwargs: Additional arguments for json.dump
    """
    # First sanitize the data
    safe_data = sanitize_for_json(data)
    
    # Then dump with safe encoder
    json.dump(safe_data, fp, cls=SafeJSONEncoder, **kwargs)


# Test the module
if __name__ == "__main__":
    test_data = {
        'normal_ratio': 1.5,
        'inf_ratio': float('inf'),
        'neg_inf_ratio': float('-inf'),
        'nan_value': float('nan'),
        'zero_shorts': safe_ratio(10, 0),
        'zero_longs': safe_ratio(0, 10),
        'zero_both': safe_ratio(0, 0),
        'nested': {
            'list_with_inf': [1, 2, float('inf'), 4],
            'string_inf': 'inf',
            'normal': 42
        }
    }
    
    print("Original data (with special values):")
    print(test_data)
    
    print("\nSanitized data:")
    sanitized = sanitize_for_json(test_data)
    print(sanitized)
    
    print("\nJSON string:")
    json_str = safe_json_dumps(test_data, indent=2)
    print(json_str)
    
    print("\nParsed back:")
    parsed = json.loads(json_str)
    print(parsed)