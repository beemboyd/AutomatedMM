#!/usr/bin/env python
"""
Utility script to generate launchd plist files for scheduling trading system components
on macOS systems.
"""

import os
import sys
import argparse
from pathlib import Path
from string import Template


def parse_arguments():
    """Parse command line arguments for plist generation"""
    parser = argparse.ArgumentParser(description="Generate launchd plist files for scheduling India-TS components")
    parser.add_argument(
        '-o', '--output-dir',
        default='./plist',
        help='Directory where plist files will be created (default: ./plist)'
    )
    parser.add_argument(
        '-p', '--python-path',
        default=None,
        help='Path to Python interpreter (default: auto-detected)'
    )
    parser.add_argument(
        '-s', '--scripts-dir',
        default=None,
        help='Path to scripts directory (default: auto-detected)'
    )
    parser.add_argument(
        '-u', '--user',
        default=None,
        help='Username to run the jobs (default: current user)'
    )
    return parser.parse_args()


def get_python_path(user_provided=None):
    """Get the path to the Python interpreter"""
    if user_provided:
        return user_provided
    
    # Try to use the current Python interpreter
    return sys.executable


def get_scripts_dir(user_provided=None):
    """Get the path to the scripts directory"""
    if user_provided:
        return Path(user_provided).resolve()
    
    # Try to determine from script location
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    scripts_dir = project_root / 'scripts'
    
    if scripts_dir.exists():
        return scripts_dir
    else:
        raise ValueError("Could not determine scripts directory. Please provide it with --scripts-dir")


def get_current_user(user_provided=None):
    """Get the current username"""
    if user_provided:
        return user_provided
    
    import getpass
    return getpass.getuser()


def create_plist_content(label, command, start_interval, username):
    """Create the content for a launchd plist file"""
    template = Template('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${command}</string>
    </array>
    <key>StartInterval</key>
    <integer>${start_interval}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/${label}.stdout</string>
    <key>StandardErrorPath</key>
    <string>/tmp/${label}.stderr</string>
    <key>UserName</key>
    <string>${username}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Hour</key>
            <integer>9</integer>
            <key>Minute</key>
            <integer>15</integer>
            <key>Weekday</key>
            <integer>1</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>9</integer>
            <key>Minute</key>
            <integer>15</integer>
            <key>Weekday</key>
            <integer>2</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>9</integer>
            <key>Minute</key>
            <integer>15</integer>
            <key>Weekday</key>
            <integer>3</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>9</integer>
            <key>Minute</key>
            <integer>15</integer>
            <key>Weekday</key>
            <integer>4</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>9</integer>
            <key>Minute</key>
            <integer>15</integer>
            <key>Weekday</key>
            <integer>5</integer>
        </dict>
    </array>
</dict>
</plist>''')
    
    return template.substitute(
        label=label,
        command=command,
        start_interval=start_interval,
        username=username
    )


def create_plist_files(python_path, scripts_dir, output_dir, username):
    """Create plist files for scheduling the trading system components"""
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Define the jobs to schedule
    jobs = [
        {
            'label': 'com.indiaTS.market_scan',
            'script': 'scan_market.py',
            'interval': 300,  # Every 5 minutes
            'description': 'Market Scanner'
        },
        {
            'label': 'com.indiaTS.place_orders',
            'script': 'place_orders.py',
            'interval': 600,  # Every 10 minutes
            'description': 'Order Placement'
        },
        {
            'label': 'com.indiaTS.manage_risk',
            'script': 'manage_risk.py',
            'interval': 120,  # Every 2 minutes
            'description': 'Risk Management'
        }
    ]
    
    created_files = []
    
    for job in jobs:
        command = f"{python_path} {Path(scripts_dir) / job['script']}"
        plist_content = create_plist_content(
            job['label'],
            command,
            job['interval'],
            username
        )
        
        plist_file = Path(output_dir) / f"{job['label']}.plist"
        with open(plist_file, 'w') as f:
            f.write(plist_content)
        
        created_files.append((plist_file, job['description']))
    
    return created_files


def main():
    """Main function"""
    args = parse_arguments()
    
    try:
        python_path = get_python_path(args.python_path)
        scripts_dir = get_scripts_dir(args.scripts_dir)
        username = get_current_user(args.user)
        
        print(f"Using Python: {python_path}")
        print(f"Scripts directory: {scripts_dir}")
        print(f"Output directory: {args.output_dir}")
        print(f"Username: {username}")
        print()
        
        created_files = create_plist_files(
            python_path,
            scripts_dir,
            args.output_dir,
            username
        )
        
        print(f"Successfully created {len(created_files)} plist files:")
        for file_path, description in created_files:
            print(f"  - {file_path} ({description})")
        
        print("\nTo install the launchd jobs, run the following commands:")
        for file_path, _ in created_files:
            print(f"  launchctl load -w {file_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()