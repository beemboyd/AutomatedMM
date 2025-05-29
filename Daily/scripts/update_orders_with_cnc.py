#!/usr/bin/env python
"""
Update Orders Files with CNC Positions Script
=============================================
This script updates existing orders files to include current CNC positions from broker.
This ensures the watchdog monitors actual holdings instead of just daily orders.
"""

import os
import sys
import json
import datetime
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def update_orders_file_with_cnc(user_name: str, orders_file: str, cnc_positions: List[Dict]) -> bool:
    """Update orders file to include CNC positions"""
    try:
        # Load existing orders file
        with open(orders_file, 'r') as f:
            orders_data = json.load(f)
        
        # Create backup
        backup_file = orders_file.replace('.json', '_backup.json')
        with open(backup_file, 'w') as f:
            json.dump(orders_data, f, indent=2)
        
        # Add CNC positions as completed orders
        existing_orders = orders_data.get('orders', [])
        
        for pos in cnc_positions:
            if pos['quantity'] > 0:  # Only long positions
                cnc_order = {
                    "order_id": f"CNC_{pos['tradingsymbol']}",
                    "tradingsymbol": pos['tradingsymbol'],
                    "exchange": pos.get('exchange', 'NSE'),
                    "instrument_token": pos.get('instrument_token', 0),
                    "transaction_type": "BUY",
                    "product": "CNC",
                    "order_type": "MARKET",
                    "quantity": abs(pos['quantity']),
                    "filled_quantity": abs(pos['quantity']),
                    "price": pos['average_price'],
                    "average_price": pos['average_price'],
                    "status": "COMPLETE",
                    "order_timestamp": datetime.datetime.now().isoformat(),
                    "status_message": "CNC position imported from broker",
                    "data_source": pos.get('source', 'broker'),
                    "notes": "Added by CNC sync script for watchdog monitoring"
                }
                existing_orders.append(cnc_order)
        
        # Update orders data
        orders_data['orders'] = existing_orders
        orders_data['metadata']['last_cnc_sync'] = datetime.datetime.now().isoformat()
        orders_data['metadata']['cnc_positions_added'] = len([p for p in cnc_positions if p['quantity'] > 0])
        
        # Save updated file
        with open(orders_file, 'w') as f:
            json.dump(orders_data, f, indent=2)
        
        print(f"✅ Updated {orders_file} with {len([p for p in cnc_positions if p['quantity'] > 0])} CNC positions")
        print(f"📁 Backup saved to: {backup_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating {orders_file}: {e}")
        return False

if __name__ == "__main__":
    # Quick update - run the CNC sync and update orders files
    print("🔄 Running CNC sync and updating orders files...")
    
    # Import the CNC sync script
    from synch_zerodha_cnc_positions import ZerodhaCNCPositionsSynchronizer
    
    try:
        synchronizer = ZerodhaCNCPositionsSynchronizer()
        sync_result = synchronizer.sync_all_users()
        
        # Update orders files for each user
        for user_result in sync_result['user_results']:
            if user_result['success']:
                user_name = user_result['user']
                orders_file = synchronizer.get_latest_orders_file(user_name)
                
                if orders_file:
                    # Get CNC positions for this user
                    cnc_positions = synchronizer.get_broker_cnc_positions(user_name)
                    
                    # Update the orders file
                    success = update_orders_file_with_cnc(user_name, orders_file, cnc_positions)
                    
                    if success:
                        print(f"✅ {user_name}: Orders file updated with CNC positions")
                    else:
                        print(f"❌ {user_name}: Failed to update orders file")
        
        print("\n🎯 Now restart the watchdogs to monitor updated positions:")
        print("   ./manage_watchdogs.sh restart")
        
    except Exception as e:
        print(f"❌ Update failed: {e}")