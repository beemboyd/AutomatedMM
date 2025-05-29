#!/usr/bin/env python3
"""
One-time utility script to migrate from multiple state files to a consolidated state file.
This script will:
1. Read all existing state files
2. Create a new consolidated state file
3. Make backup copies of the original files
"""

import os
import json
import shutil
import logging
import datetime
import argparse
from typing import Dict, List, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("state_migration")

def parse_arguments():
    parser = argparse.ArgumentParser(description="Migrate state files to consolidated format")
    parser.add_argument("--data-dir", default="data", help="Path to data directory")
    parser.add_argument("--backup", action="store_true", help="Create backup of original files")
    parser.add_argument("--force", action="store_true", help="Force migration even if target file exists")
    return parser.parse_args()

def main():
    args = parse_arguments()
    data_dir = args.data_dir
    
    # Validate data directory
    if not os.path.isdir(data_dir):
        logger.error(f"Data directory not found: {data_dir}")
        return
    
    # Source files
    position_file = os.path.join(data_dir, 'position_data.json')
    gtt_file = os.path.join(data_dir, 'gttz_gtt_tracker.json')
    long_file = os.path.join(data_dir, 'long_positions.txt')
    short_file = os.path.join(data_dir, 'short_positions.txt')
    daily_file = os.path.join(data_dir, 'daily_ticker_tracker.json')
    
    # Target file
    target_file = os.path.join(data_dir, 'trading_state.json')
    
    # Check if target file already exists
    if os.path.exists(target_file) and not args.force:
        logger.error(f"Target file already exists: {target_file}")
        logger.error("Use --force to overwrite")
        return
    
    # Initialize state structure
    state = {
        "meta": {
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "last_updated": datetime.datetime.now().isoformat(),
            "migration_date": datetime.datetime.now().isoformat()
        },
        "positions": {},
        "daily_tickers": {
            "long": [],
            "short": []
        }
    }
    
    # Migrate position_data.json
    if os.path.exists(position_file):
        logger.info(f"Migrating position data from {position_file}")
        try:
            with open(position_file, 'r') as f:
                position_data = json.load(f)
                
            for ticker, data in position_data.items():
                if ticker not in state["positions"]:
                    state["positions"][ticker] = {
                        "type": data.get("type", ""),
                        "entry_price": data.get("entry_price", 0),
                        "best_price": data.get("best_price", 0),
                        "quantity": 0,  # Will be updated from position files
                        "timestamp": datetime.datetime.now().isoformat()
                    }
            logger.info(f"Migrated {len(position_data)} positions")
        except Exception as e:
            logger.error(f"Error migrating position data: {e}")
    
    # Migrate GTT data
    if os.path.exists(gtt_file):
        logger.info(f"Migrating GTT data from {gtt_file}")
        try:
            with open(gtt_file, 'r') as f:
                gtt_data = json.load(f)
            
            migrated_count = 0
            for ticker, data in gtt_data.items():
                if ticker in state["positions"]:
                    state["positions"][ticker]["gtt"] = {
                        "trigger_id": data.get("trigger_id"),
                        "trigger_price": data.get("trigger_price"),
                        "timestamp": data.get("timestamp", datetime.datetime.now().isoformat())
                    }
                    migrated_count += 1
                else:
                    # Create position entry if it doesn't exist
                    state["positions"][ticker] = {
                        "type": data.get("position_type", ""),
                        "entry_price": 0,
                        "best_price": 0,
                        "quantity": 0,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "gtt": {
                            "trigger_id": data.get("trigger_id"),
                            "trigger_price": data.get("trigger_price"),
                            "timestamp": data.get("timestamp", datetime.datetime.now().isoformat())
                        }
                    }
                    migrated_count += 1
            logger.info(f"Migrated {migrated_count} GTT records")
        except Exception as e:
            logger.error(f"Error migrating GTT data: {e}")
    
    # Migrate long positions
    if os.path.exists(long_file):
        logger.info(f"Migrating long positions from {long_file}")
        try:
            with open(long_file, 'r') as f:
                lines = f.readlines()
            
            migrated_count = 0
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                parts = line.split(':')
                if len(parts) >= 2:
                    ticker = parts[0]
                    try:
                        quantity = int(parts[1])
                        timestamp = parts[2] if len(parts) > 2 else datetime.datetime.now().isoformat()
                        
                        if ticker in state["positions"]:
                            state["positions"][ticker]["quantity"] = quantity
                            state["positions"][ticker]["timestamp"] = timestamp
                            state["positions"][ticker]["type"] = "LONG"
                        else:
                            state["positions"][ticker] = {
                                "type": "LONG",
                                "entry_price": 0,
                                "best_price": 0,
                                "quantity": quantity,
                                "timestamp": timestamp
                            }
                        migrated_count += 1
                    except ValueError:
                        logger.warning(f"Skipping invalid line in {long_file}: {line}")
            logger.info(f"Migrated {migrated_count} long positions")
        except Exception as e:
            logger.error(f"Error migrating long positions: {e}")
    
    # Migrate short positions
    if os.path.exists(short_file):
        logger.info(f"Migrating short positions from {short_file}")
        try:
            with open(short_file, 'r') as f:
                lines = f.readlines()
            
            migrated_count = 0
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                parts = line.split(':')
                if len(parts) >= 2:
                    ticker = parts[0]
                    try:
                        quantity = int(parts[1])
                        timestamp = parts[2] if len(parts) > 2 else datetime.datetime.now().isoformat()
                        
                        if ticker in state["positions"]:
                            state["positions"][ticker]["quantity"] = quantity
                            state["positions"][ticker]["timestamp"] = timestamp
                            state["positions"][ticker]["type"] = "SHORT"
                        else:
                            state["positions"][ticker] = {
                                "type": "SHORT",
                                "entry_price": 0,
                                "best_price": 0,
                                "quantity": quantity,
                                "timestamp": timestamp
                            }
                        migrated_count += 1
                    except ValueError:
                        logger.warning(f"Skipping invalid line in {short_file}: {line}")
            logger.info(f"Migrated {migrated_count} short positions")
        except Exception as e:
            logger.error(f"Error migrating short positions: {e}")
    
    # Migrate daily tickers
    if os.path.exists(daily_file):
        logger.info(f"Migrating daily tickers from {daily_file}")
        try:
            with open(daily_file, 'r') as f:
                daily_data = json.load(f)
            
            # Only migrate if it's from today
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            if daily_data.get("date") == today:
                state["daily_tickers"]["long"] = daily_data.get("long_tickers", [])
                state["daily_tickers"]["short"] = daily_data.get("short_tickers", [])
                logger.info(f"Migrated daily tickers for {today}")
            else:
                logger.info(f"Daily tickers are from {daily_data.get('date')}, not today ({today}). Using empty lists.")
        except Exception as e:
            logger.error(f"Error migrating daily tickers: {e}")
    
    # Create backups if requested
    if args.backup:
        backup_dir = os.path.join(data_dir, "backup_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.makedirs(backup_dir, exist_ok=True)
        logger.info(f"Creating backups in {backup_dir}")
        
        for file_path in [position_file, gtt_file, long_file, short_file, daily_file]:
            if os.path.exists(file_path):
                backup_path = os.path.join(backup_dir, os.path.basename(file_path))
                try:
                    shutil.copy2(file_path, backup_path)
                    logger.info(f"Backed up {file_path} to {backup_path}")
                except Exception as e:
                    logger.error(f"Failed to backup {file_path}: {e}")
    
    # Write the consolidated state file
    try:
        with open(target_file, 'w') as f:
            json.dump(state, f, indent=2)
        logger.info(f"Successfully wrote consolidated state to {target_file}")
    except Exception as e:
        logger.error(f"Error writing consolidated state to {target_file}: {e}")
    
    # Print migration summary
    position_count = len(state["positions"])
    gtt_count = sum(1 for pos in state["positions"].values() if "gtt" in pos)
    long_count = sum(1 for pos in state["positions"].values() if pos.get("type") == "LONG" and pos.get("quantity", 0) > 0)
    short_count = sum(1 for pos in state["positions"].values() if pos.get("type") == "SHORT" and pos.get("quantity", 0) > 0)
    
    logger.info("Migration Summary:")
    logger.info(f"- Total positions: {position_count}")
    logger.info(f"- GTT records: {gtt_count}")
    logger.info(f"- Long positions: {long_count}")
    logger.info(f"- Short positions: {short_count}")
    logger.info(f"- Daily tickers: {len(state['daily_tickers']['long'])} long, {len(state['daily_tickers']['short'])} short")

if __name__ == "__main__":
    main()