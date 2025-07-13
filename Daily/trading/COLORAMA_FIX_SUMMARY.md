# Fix Summary: sell_all_cnc_positions.py

## Issue
The script was failing with `ModuleNotFoundError: No module named 'colorama'`

## Solution
Replaced the colorama dependency with a simple ANSI color code implementation that:

1. **Removed External Dependency**: No longer requires `pip install colorama`
2. **Maintains Color Support**: Uses standard ANSI escape codes for colored output
3. **Graceful Degradation**: Automatically disables colors in non-TTY environments
4. **Fallback for Tabulate**: Added fallback display method if tabulate is not installed

## Changes Made

### 1. Replaced Colorama Import
```python
# OLD
from colorama import init, Fore, Back, Style

# NEW
# Simple color class with ANSI codes
class Fore:
    RED = '\033[91m'
    GREEN = '\033[92m'
    # etc...
```

### 2. Added Color Support Detection
```python
SUPPORTS_COLOR = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
```

### 3. Made Tabulate Optional
```python
try:
    from tabulate import tabulate
except ImportError:
    tabulate = None
```

### 4. Fixed Import Paths
```python
try:
    from utils.broker_interface import BrokerInterface
except ImportError:
    # Fallback import with path adjustment
```

## Result
The script now runs without requiring colorama installation while maintaining the same colored output functionality when supported by the terminal.

## To Run
```bash
/Users/maverick/PycharmProjects/India-TS/.venv/bin/python /Users/maverick/PycharmProjects/India-TS/Daily/trading/sell_all_cnc_positions.py
```