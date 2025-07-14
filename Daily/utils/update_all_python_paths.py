#!/usr/bin/env python3
"""Update all India-TS plist files to use /usr/bin/python3"""

import os
import subprocess
import plistlib

# Target Python path as requested
TARGET_PYTHON = "/usr/bin/python3"

# LaunchAgents directory
LAUNCHAGENTS_DIR = "/Users/maverick/Library/LaunchAgents"

# Get all India-TS plist files
plist_files = [f for f in os.listdir(LAUNCHAGENTS_DIR) 
               if f.startswith("com.india-ts.") and f.endswith(".plist")]

print(f"Updating {len(plist_files)} India-TS plist files to use {TARGET_PYTHON}")
print("=" * 60)

updated_count = 0
skipped_count = 0
failed_count = 0

for plist_file in sorted(plist_files):
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
                if current_python == TARGET_PYTHON:
                    print(f"{plist_file}: Already using {TARGET_PYTHON}")
                    skipped_count += 1
                else:
                    print(f"{plist_file}: Updating from {current_python}")
                    
                    # Update to target Python
                    plist_data['ProgramArguments'][0] = TARGET_PYTHON
                    
                    # Write back
                    with open(plist_path, 'wb') as f:
                        plistlib.dump(plist_data, f)
                    
                    updated_count += 1
                    
                    # Reload if currently loaded
                    job_name = plist_file.replace('.plist', '')
                    result = subprocess.run(['launchctl', 'list'], 
                                          capture_output=True, text=True)
                    
                    if job_name in result.stdout:
                        subprocess.run(['launchctl', 'unload', plist_path], 
                                     capture_output=True)
                        subprocess.run(['launchctl', 'load', plist_path], 
                                     capture_output=True)
                        print(f"  Reloaded {job_name}")
            else:
                print(f"{plist_file}: Not a Python job (skipped)")
                skipped_count += 1
                
    except Exception as e:
        print(f"{plist_file}: ERROR - {str(e)}")
        failed_count += 1

print("\n" + "=" * 60)
print(f"Summary: {updated_count} updated, {skipped_count} skipped, {failed_count} failed")
print(f"All plist files now use: {TARGET_PYTHON}")

# Verify
print("\nVerifying Python paths:")
print("-" * 30)
subprocess.run([
    "bash", "-c",
    "for plist in ~/Library/LaunchAgents/com.india-ts.*.plist; do "
    "plutil -p \"$plist\" | grep -E 'python' | head -1; "
    "done | sort | uniq -c"
])