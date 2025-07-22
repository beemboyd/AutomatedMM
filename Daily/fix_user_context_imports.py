#!/usr/bin/env python3
"""
Fix imports in user_context_manager.py to work with local modules
"""

import re

def fix_imports():
    filepath = 'user_context_manager.py'
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace import patterns
    replacements = [
        (r'from state_manager import StateManager',
         'try:\n        from .state_manager import StateManager\n    except ImportError:\n        from state_manager import StateManager'),
        (r'from order_manager import OrderManager',
         'try:\n        from .order_manager import OrderManager\n    except ImportError:\n        from order_manager import OrderManager'),
        (r'from config import Config',
         'try:\n        from .config import Config\n    except ImportError:\n        from config import Config, get_config'),
    ]
    
    for old, new in replacements:
        content = re.sub(old, new, content)
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print("Fixed imports in user_context_manager.py")

if __name__ == "__main__":
    fix_imports()