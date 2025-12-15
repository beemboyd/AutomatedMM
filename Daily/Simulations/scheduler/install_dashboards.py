#!/usr/bin/env python3
"""
Install/Uninstall Simulation Dashboard LaunchAgents
"""

import os
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent
PLISTS_DIR = BASE_DIR / 'plists'
LAUNCH_AGENTS_DIR = Path.home() / 'Library' / 'LaunchAgents'

DASHBOARD_PLISTS = [
    'com.india-ts.simulation-dashboard-1.plist',
    'com.india-ts.simulation-dashboard-2.plist',
    'com.india-ts.simulation-dashboard-3.plist',
    'com.india-ts.simulation-dashboard-4.plist',
]


def install_plists():
    """Install all dashboard plists to LaunchAgents"""
    print("Installing Simulation Dashboard LaunchAgents...")

    # Create logs directory
    logs_dir = BASE_DIR.parent / 'logs'
    logs_dir.mkdir(exist_ok=True)

    for plist_name in DASHBOARD_PLISTS:
        src = PLISTS_DIR / plist_name
        dst = LAUNCH_AGENTS_DIR / plist_name

        if not src.exists():
            print(f"  [SKIP] {plist_name} not found")
            continue

        # Unload if already loaded
        if dst.exists():
            subprocess.run(['launchctl', 'unload', str(dst)], capture_output=True)

        # Copy plist
        shutil.copy(src, dst)
        print(f"  [COPY] {plist_name}")

        # Load plist
        result = subprocess.run(['launchctl', 'load', str(dst)], capture_output=True)
        if result.returncode == 0:
            print(f"  [LOAD] {plist_name} loaded successfully")
        else:
            print(f"  [WARN] {plist_name} load failed: {result.stderr.decode()}")

    print("\nDashboards installed and started:")
    print("  Sim 1 (Long + KC Lower):  http://localhost:4001")
    print("  Sim 2 (Long + PSAR):      http://localhost:4002")
    print("  Sim 3 (Short + KC Upper): http://localhost:4003")
    print("  Sim 4 (Short + PSAR):     http://localhost:4004")


def uninstall_plists():
    """Uninstall all dashboard plists from LaunchAgents"""
    print("Uninstalling Simulation Dashboard LaunchAgents...")

    for plist_name in DASHBOARD_PLISTS:
        dst = LAUNCH_AGENTS_DIR / plist_name

        if dst.exists():
            # Unload
            subprocess.run(['launchctl', 'unload', str(dst)], capture_output=True)
            # Remove
            dst.unlink()
            print(f"  [REMOVE] {plist_name}")
        else:
            print(f"  [SKIP] {plist_name} not installed")

    print("\nDashboards uninstalled")


def status():
    """Show status of dashboard LaunchAgents"""
    print("Simulation Dashboard Status:")
    print("-" * 50)

    for i, plist_name in enumerate(DASHBOARD_PLISTS, 1):
        label = plist_name.replace('.plist', '')
        result = subprocess.run(
            ['launchctl', 'list', label],
            capture_output=True
        )

        if result.returncode == 0:
            lines = result.stdout.decode().strip().split('\n')
            if len(lines) > 1:
                pid = lines[1].split()[0]
                status = "RUNNING" if pid != '-' else "STOPPED"
            else:
                status = "LOADED"
            print(f"  Dashboard {i} (port 400{i}): {status}")
        else:
            print(f"  Dashboard {i} (port 400{i}): NOT INSTALLED")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Manage Simulation Dashboard LaunchAgents')
    parser.add_argument('action', choices=['install', 'uninstall', 'status', 'restart'],
                       help='Action to perform')
    args = parser.parse_args()

    if args.action == 'install':
        install_plists()
    elif args.action == 'uninstall':
        uninstall_plists()
    elif args.action == 'restart':
        uninstall_plists()
        install_plists()
    elif args.action == 'status':
        status()


if __name__ == '__main__':
    main()
