#!/usr/bin/env python3
"""
Install/Restore India-TS plist files from backup
This script ensures all scheduled jobs are properly installed with correct namespaces
"""

import os
import shutil
import subprocess
import glob
import sys

def main():
    """Install all India-TS plist files from backup directory"""
    
    # Define paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backup_dir = os.path.join(script_dir, 'plists')
    target_dir = '/Users/maverick/Library/LaunchAgents'
    
    # Check if backup directory exists
    if not os.path.exists(backup_dir):
        print(f"Error: Backup directory not found: {backup_dir}")
        sys.exit(1)
    
    # Find all India-TS plist files
    plist_pattern = os.path.join(backup_dir, 'com.india-ts.*.plist')
    plist_files = glob.glob(plist_pattern)
    
    if not plist_files:
        print(f"No India-TS plist files found in {backup_dir}")
        sys.exit(1)
    
    print(f"Found {len(plist_files)} India-TS plist files to install")
    print("-" * 60)
    
    # Track results
    installed = []
    failed = []
    
    for plist_path in sorted(plist_files):
        plist_name = os.path.basename(plist_path)
        target_path = os.path.join(target_dir, plist_name)
        job_id = plist_name.replace('.plist', '')
        
        try:
            # First unload if it exists
            subprocess.run(['launchctl', 'unload', target_path], 
                         capture_output=True, text=True)
            
            # Copy the plist file
            shutil.copy2(plist_path, target_path)
            print(f"✓ Copied {plist_name}")
            
            # Load the job
            result = subprocess.run(['launchctl', 'load', target_path], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✓ Loaded {job_id}")
                installed.append(job_id)
            else:
                print(f"✗ Failed to load {job_id}: {result.stderr}")
                failed.append((job_id, result.stderr))
                
        except Exception as e:
            print(f"✗ Error installing {plist_name}: {str(e)}")
            failed.append((plist_name, str(e)))
        
        print("-" * 60)
    
    # Summary
    print("\nInstallation Summary:")
    print(f"Successfully installed: {len(installed)} jobs")
    print(f"Failed: {len(failed)} jobs")
    
    if installed:
        print("\nInstalled jobs:")
        for job in installed:
            print(f"  - {job}")
    
    if failed:
        print("\nFailed installations:")
        for job, error in failed:
            print(f"  - {job}: {error}")
    
    # Verify installation
    print("\nVerifying installation...")
    verify_count = 0
    for job_id in installed:
        result = subprocess.run(['launchctl', 'list', job_id], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            verify_count += 1
    
    print(f"Verified {verify_count}/{len(installed)} jobs are loaded")
    
    return 0 if not failed else 1

if __name__ == '__main__':
    sys.exit(main())