#!/usr/bin/env python3
"""
Fix import issues specifically for watchdog scripts and other executable files
"""

import os
import glob

def fix_file(filepath):
    """Fix imports in a single file"""
    print(f"Fixing {filepath}...")
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    modified = False
    new_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Look for the problematic import
        if 'from ..user_context_manager import' in line:
            # Find the end of the import statement (handles multi-line imports)
            import_lines = [line]
            j = i + 1
            while j < len(lines) and (')' not in lines[j-1] or lines[j-1].strip().endswith(',')):
                import_lines.append(lines[j])
                j += 1
            
            # Add sys.path if not already there
            if i > 0 and 'sys.path.insert' not in lines[i-1]:
                new_lines.append('# Add Daily to path for imports\n')
                new_lines.append('sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n')
                new_lines.append('\n')
            
            # Replace with direct import
            new_lines.append('from user_context_manager import (\n')
            new_lines.append('    get_context_manager,\n')
            new_lines.append('    get_user_data_handler,\n')
            new_lines.append('    UserCredentials\n')
            new_lines.append(')\n')
            
            i = j
            modified = True
            continue
        
        new_lines.append(line)
        i += 1
    
    if modified:
        with open(filepath, 'w') as f:
            f.writelines(new_lines)
        print(f"  ✓ Fixed imports in {os.path.basename(filepath)}")
        return True
    else:
        print(f"  - No changes needed in {os.path.basename(filepath)}")
        return False

def main():
    """Fix imports in watchdog files and other executables"""
    daily_path = os.path.dirname(os.path.abspath(__file__))
    
    # List of files that are commonly executed directly
    target_files = [
        'portfolio/SL_watchdog.py',
        'portfolio/SL_watchdog_modified.py',
        'portfolio/SL_watchdog_with_vsr.py',
        'portfolio/position_watchdog.py',
        'trading/place_orders.py',
        'trading/place_orders_daily.py',
        'trading/place_orders_FNO.py',
        'trading/place_orders_FNO_advanced.py',
        'trading/place_orders_FNO_wheel.py',
        'scanners/scan_market.py',
        'analysis/Action_plan.py',
    ]
    
    fixed_count = 0
    
    for target in target_files:
        filepath = os.path.join(daily_path, target)
        if os.path.exists(filepath):
            if fix_file(filepath):
                fixed_count += 1
        else:
            print(f"  ! File not found: {target}")
    
    print(f"\nTotal files fixed: {fixed_count}")
    print("\nThe watchdog scripts should now run without import errors.")

if __name__ == "__main__":
    main()