#!/usr/local/bin/python3
"""
Run the Market Regime Dashboard (Enhanced Version)

This script starts the enhanced web-based dashboard with advanced features including:
- Subtle regime change detection
- Market score proximity indicators
- Delta tracking for all metrics
- Enhanced volatility analysis
- Real-time sparkline visualizations
"""

import sys
import os
import logging
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Market_Regime.dashboard.regime_dashboard_enhanced import RegimeDashboardApp


def setup_logging(log_level='INFO'):
    """Setup logging configuration"""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'dashboard_{datetime.now().strftime("%Y%m%d")}.log')
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Run Market Regime Dashboard (Enhanced)')
    parser.add_argument('--host', default='localhost', help='Host to run dashboard on')
    parser.add_argument('--port', type=int, default=8080, help='Port to run dashboard on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    logger = logging.getLogger(__name__)
    logger.info("Starting Market Regime Dashboard (Enhanced Version)")
    logger.info(f"Dashboard URL: http://{args.host}:{args.port}")
    
    print("\n" + "="*60)
    print("MARKET REGIME DASHBOARD - ENHANCED VERSION")
    print("="*60)
    print(f"\nStarting dashboard at: http://{args.host}:{args.port}")
    print("\nFeatures:")
    print("- Subtle regime change detection")
    print("- Market score proximity indicators")
    print("- Delta tracking for all metrics")
    print("- Enhanced volatility analysis")
    print("- Real-time sparkline visualizations")
    print("- Historical data API endpoint")
    print("\nPress Ctrl+C to stop the dashboard")
    print("="*60 + "\n")
    
    try:
        # Create and run enhanced dashboard
        dashboard = RegimeDashboardApp(host=args.host, port=args.port)
        dashboard.run()
    except KeyboardInterrupt:
        print("\n\nDashboard stopped by user")
        logger.info("Dashboard stopped by user")
    except Exception as e:
        logger.error(f"Error running dashboard: {e}")
        raise


if __name__ == '__main__':
    main()