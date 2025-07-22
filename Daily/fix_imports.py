#!/usr/bin/env python3
"""
Fix import issues for self-contained Daily folder
This script updates all Python files to handle both relative and direct execution
"""

import os
import re

def fix_imports_in_file(filepath):
    """Fix imports in a single file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if file has the relative import
    if 'from ..user_context_manager import' not in content:
        return False
    
    # Pattern to find the import block
    pattern = r'(# sys\.path\.insert.*?\n)(.*?)(from \.\.user_context_manager import \([\s\S]*?\))'
    
    # Replacement that adds try/except block
    replacement = r'''\1# For self-contained Daily folder, add Daily to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

\2try:
    # Try relative import first (when imported as module)
    \3
except ImportError:
    # Fall back to absolute import (when run directly)
    from user_context_manager import (
        get_context_manager,
        get_user_data_handler,
        UserCredentials
    )'''
    
    # Apply the replacement
    new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    # Handle cases where there's no sys.path.insert comment
    if new_content == content and 'from ..user_context_manager import' in content:
        # Find the import statement
        import_pattern = r'(from \.\.user_context_manager import \([\s\S]*?\))'
        
        replacement2 = r'''# Add Daily to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    # Try relative import first (when imported as module)
    \1
except ImportError:
    # Fall back to absolute import (when run directly)
    from user_context_manager import (
        get_context_manager,
        get_user_data_handler,
        UserCredentials
    )'''
        
        new_content = re.sub(import_pattern, replacement2, content, flags=re.MULTILINE)
    
    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        return True
    
    return False

def fix_all_imports():
    """Fix imports in all Python files in Daily folder"""
    daily_path = os.path.dirname(os.path.abspath(__file__))
    fixed_count = 0
    
    for root, dirs, files in os.walk(daily_path):
        for file in files:
            if file.endswith('.py') and file != 'fix_imports.py':
                filepath = os.path.join(root, file)
                try:
                    if fix_imports_in_file(filepath):
                        print(f"Fixed: {os.path.relpath(filepath, daily_path)}")
                        fixed_count += 1
                except Exception as e:
                    print(f"Error fixing {filepath}: {e}")
    
    print(f"\nTotal files fixed: {fixed_count}")

if __name__ == "__main__":
    fix_all_imports()