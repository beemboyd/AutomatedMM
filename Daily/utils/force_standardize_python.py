#!/usr/bin/env python3
"""Force standardize all Python paths in India-TS plist files"""

import os
import subprocess
import plistlib

# Target Python path (virtual env with all modules)
TARGET_PYTHON = "/Users/maverick/PycharmProjects/India-TS/.venv/bin/python"

# LaunchAgents directory
LAUNCHAGENTS_DIR = "/Users/maverick/Library/LaunchAgents"

# Get all India-TS plist files
plist_files = [f for f in os.listdir(LAUNCHAGENTS_DIR) 
               if f.startswith("com.india-ts.") and f.endswith(".plist")]

print(f"Found {len(plist_files)} India-TS plist files")
print(f"Target Python: {TARGET_PYTHON}")
print("=" * 60)

updated_count = 0
failed_count = 0

for plist_file in plist_files:
    plist_path = os.path.join(LAUNCHAGENTS_DIR, plist_file)
    
    try:
        # Read plist
        with open(plist_path, 'rb') as f:
            plist_data = plistlib.load(f)
        
        # Check if it has ProgramArguments
        if 'ProgramArguments' in plist_data and len(plist_data['ProgramArguments']) > 0:
            current_python = plist_data['ProgramArguments'][0]
            
            # Check if first argument is a Python interpreter
            if 'python' in current_python.lower():
                print(f"\n{plist_file}:")
                print(f"  Current: {current_python}")
                
                # Update to target Python
                plist_data['ProgramArguments'][0] = TARGET_PYTHON
                
                # Write back
                with open(plist_path, 'wb') as f:
                    plistlib.dump(plist_data, f)
                
                print(f"  Updated: {TARGET_PYTHON}")
                updated_count += 1
                
                # Reload if currently loaded
                job_name = plist_file.replace('.plist', '')
                is_loaded = subprocess.run(['launchctl', 'list'], 
                                         capture_output=True, text=True).stdout
                
                if job_name in is_loaded:
                    print(f"  Reloading {job_name}...")
                    subprocess.run(['launchctl', 'unload', plist_path], 
                                 capture_output=True)
                    subprocess.run(['launchctl', 'load', plist_path], 
                                 capture_output=True)
            else:
                print(f"\n{plist_file}: Skipped (not a Python job)")
                
    except Exception as e:
        print(f"\n{plist_file}: ERROR - {str(e)}")
        failed_count += 1

print("\n" + "=" * 60)
print(f"Summary: {updated_count} updated, {failed_count} failed")
print("\nTo verify, run:")
print("for plist in ~/Library/LaunchAgents/com.india-ts.*.plist; do")
print("  plutil -p \"$plist\" | grep -E \"python\" | head -1")
print("done | sort | uniq -c")