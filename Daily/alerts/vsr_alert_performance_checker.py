#!/usr/bin/env python3
"""
VSR Alert Performance Checker

Runs daily at 9:30 AM to check if alerted tickers from the past 5 days
are currently trading above their alerted price. Sends STRONG BUY signal
via Telegram for tickers that are performing well.

Author: Claude
Date: 2025-12-09
"""

import os
import sys
import sqlite3
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_notifier import TelegramNotifier

# Setup logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'vsr_alert_performance.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class VSRAlertPerformanceChecker:
    """Checks performance of past VSR alerts and identifies STRONG BUY candidates"""

    def __init__(self, user_name: str = 'Sai', lookback_days: int = 8):
        """
        Initialize the performance checker.

        Args:
            user_name: User name for API credentials
            lookback_days: Number of days to look back for alerts (default: 5)
        """
        self.user_name = user_name
        self.lookback_days = lookback_days
        self.IST = pytz.timezone('Asia/Kolkata')

        # Database path
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(base_dir, 'data', 'audit_vsr.db')

        # Initialize Telegram notifier
        self.telegram = TelegramNotifier()

        # Initialize Kite for current prices
        self.kite = self._init_kite()

        logger.info(f"VSR Alert Performance Checker initialized")
        logger.info(f"Lookback period: {lookback_days} days")

    def _init_kite(self):
        """Initialize Kite Connect API"""
        try:
            import configparser
            from kiteconnect import KiteConnect

            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
            config = configparser.ConfigParser()
            config.read(config_path)

            credential_section = f'API_CREDENTIALS_{self.user_name}'
            api_key = config.get(credential_section, 'api_key')
            access_token = config.get(credential_section, 'access_token')

            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)

            logger.info("Kite Connect initialized successfully")
            return kite

        except Exception as e:
            logger.error(f"Error initializing Kite Connect: {e}")
            return None

    def get_business_days_ago(self, num_days: int) -> datetime:
        """
        Calculate the date that is N business days ago (excludes weekends).
        """
        current_date = datetime.now(self.IST)
        business_days_counted = 0

        while business_days_counted < num_days:
            current_date -= timedelta(days=1)
            # Monday = 0, Sunday = 6; skip Saturday (5) and Sunday (6)
            if current_date.weekday() < 5:
                business_days_counted += 1

        return current_date

    def get_alerts_from_past_days(self) -> List[Dict]:
        """
        Get unique alerts from the past N business days.
        Returns only the first alert for each ticker (earliest alert price).
        """
        alerts = []

        try:
            # Calculate date range (business days)
            end_date = datetime.now(self.IST)
            start_date = self.get_business_days_ago(self.lookback_days)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get first alert for each ticker in the lookback period
            # Using MIN to get the earliest alert for each ticker
            query = """
                SELECT
                    ticker,
                    MIN(timestamp) as first_alert_time,
                    current_price as alerted_price,
                    momentum,
                    score,
                    liquidity_grade
                FROM telegram_alerts
                WHERE timestamp >= ?
                  AND timestamp <= ?
                  AND current_price > 0
                  AND momentum > 0
                GROUP BY ticker
                ORDER BY first_alert_time DESC
            """

            cursor.execute(query, (start_date.isoformat(), end_date.isoformat()))
            rows = cursor.fetchall()

            # Now get the actual price at the first alert time for each ticker
            for row in rows:
                ticker = row[0]
                first_alert_time = row[1]

                # Get the price at that specific timestamp
                price_query = """
                    SELECT current_price, momentum, score, liquidity_grade
                    FROM telegram_alerts
                    WHERE ticker = ? AND timestamp = ?
                """
                cursor.execute(price_query, (ticker, first_alert_time))
                price_row = cursor.fetchone()

                if price_row:
                    alerts.append({
                        'ticker': ticker,
                        'alert_date': first_alert_time,
                        'alerted_price': price_row[0],
                        'momentum_at_alert': price_row[1],
                        'score_at_alert': price_row[2],
                        'liquidity_grade': price_row[3]
                    })

            conn.close()

            logger.info(f"Found {len(alerts)} unique tickers alerted in past {self.lookback_days} business days")
            return alerts

        except Exception as e:
            logger.error(f"Error fetching alerts from database: {e}")
            return []

    def get_current_prices(self, tickers: List[str]) -> Dict[str, float]:
        """Get current prices for a list of tickers"""
        prices = {}

        if not self.kite or not tickers:
            return prices

        try:
            # Format tickers for Kite API
            instruments = [f"NSE:{ticker}" for ticker in tickers]

            # Get quotes
            quotes = self.kite.quote(instruments)

            for instrument, data in quotes.items():
                ticker = instrument.replace("NSE:", "")
                ltp = data.get('last_price', 0)
                if ltp > 0:
                    prices[ticker] = ltp

            logger.info(f"Fetched current prices for {len(prices)} tickers")
            return prices

        except Exception as e:
            logger.error(f"Error fetching current prices: {e}")
            return prices

    def identify_strong_buys(self) -> List[Dict]:
        """
        Identify tickers trading above their alerted price.
        Returns list of STRONG BUY candidates.
        """
        strong_buys = []

        # Get historical alerts
        alerts = self.get_alerts_from_past_days()

        if not alerts:
            logger.info("No alerts found in lookback period")
            return strong_buys

        # Get current prices
        tickers = [alert['ticker'] for alert in alerts]
        current_prices = self.get_current_prices(tickers)

        if not current_prices:
            logger.warning("Could not fetch current prices")
            return strong_buys

        # Check each alert
        for alert in alerts:
            ticker = alert['ticker']
            alerted_price = alert['alerted_price']

            # Skip invalid data types (some older records may have corrupt data)
            if not isinstance(alerted_price, (int, float)) or alerted_price <= 0:
                logger.warning(f"Skipping {ticker}: invalid alerted_price type {type(alerted_price)}")
                continue

            if ticker not in current_prices:
                continue

            current_price = current_prices[ticker]

            # Check if current price is above alerted price
            if current_price > alerted_price:
                gain_pct = ((current_price - alerted_price) / alerted_price) * 100

                strong_buys.append({
                    'ticker': ticker,
                    'alert_date': alert['alert_date'],
                    'alerted_price': alerted_price,
                    'current_price': current_price,
                    'gain_pct': gain_pct,
                    'momentum_at_alert': alert['momentum_at_alert'],
                    'score_at_alert': alert['score_at_alert'],
                    'liquidity_grade': alert['liquidity_grade']
                })

        # Sort by gain percentage (highest first)
        strong_buys.sort(key=lambda x: x['gain_pct'], reverse=True)

        logger.info(f"Found {len(strong_buys)} STRONG BUY candidates")
        return strong_buys

    def format_alert_date(self, alert_date_str: str) -> str:
        """Format alert date for display"""
        try:
            alert_date = datetime.fromisoformat(alert_date_str)
            today = datetime.now(self.IST).date()
            alert_day = alert_date.date()

            days_ago = (today - alert_day).days

            if days_ago == 0:
                return "Today"
            elif days_ago == 1:
                return "Yesterday"
            else:
                return f"{days_ago}d ago ({alert_day.strftime('%d %b')})"

        except Exception:
            return alert_date_str[:10]

    def send_strong_buy_alert(self, strong_buys: List[Dict]) -> bool:
        """Send Telegram alert for STRONG BUY candidates"""
        if not strong_buys:
            logger.info("No STRONG BUY signals to send")
            return False

        if not self.telegram.is_configured():
            logger.warning("Telegram not configured")
            return False

        # Build message
        message = f"""🚀 <b>STRONG BUY SIGNALS</b> 🚀
<i>Alerts from past {self.lookback_days} business days trading higher</i>

"""

        for i, buy in enumerate(strong_buys[:15], 1):  # Top 15
            ticker = buy['ticker']
            alert_date = self.format_alert_date(buy['alert_date'])
            alerted_price = buy['alerted_price']
            current_price = buy['current_price']
            gain_pct = buy['gain_pct']
            liq_grade = buy.get('liquidity_grade', 'N/A')

            # Emoji based on gain
            if gain_pct >= 5:
                gain_emoji = "🔥🔥"
            elif gain_pct >= 2:
                gain_emoji = "🔥"
            else:
                gain_emoji = "📈"

            # Liquidity emoji
            liq_emoji = "💎" if liq_grade == 'A' else "💧" if liq_grade == 'B' else "💦" if liq_grade == 'C' else "⚠️"

            message += f"{i}. <b>{ticker}</b> {gain_emoji}\n"
            message += f"   📅 Alert: {alert_date} @ ₹{alerted_price:.2f}\n"
            message += f"   💰 Now: ₹{current_price:.2f} (<b>+{gain_pct:.1f}%</b>) {liq_emoji}\n\n"

        if len(strong_buys) > 15:
            message += f"<i>...and {len(strong_buys) - 15} more tickers</i>\n\n"

        message += f"⏰ {datetime.now(self.IST).strftime('%d %b %Y, %I:%M %p IST')}"

        # Send message
        success = self.telegram.send_message(message, parse_mode='HTML')

        if success:
            logger.info(f"Sent STRONG BUY alert with {len(strong_buys)} tickers")
        else:
            logger.error("Failed to send STRONG BUY alert")

        return success

    def run(self) -> bool:
        """Run the performance check and send alerts"""
        logger.info("=" * 50)
        logger.info("Starting VSR Alert Performance Check")
        logger.info("=" * 50)

        try:
            # Identify strong buys
            strong_buys = self.identify_strong_buys()

            # Send alert if we have candidates
            if strong_buys:
                success = self.send_strong_buy_alert(strong_buys)

                # Log results
                logger.info("Performance Check Results:")
                for buy in strong_buys[:10]:
                    logger.info(f"  {buy['ticker']}: Alert ₹{buy['alerted_price']:.2f} -> "
                              f"Now ₹{buy['current_price']:.2f} (+{buy['gain_pct']:.1f}%)")

                return success
            else:
                logger.info("No STRONG BUY signals found")
                return True

        except Exception as e:
            logger.error(f"Error running performance check: {e}")
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='VSR Alert Performance Checker')
    parser.add_argument('--user', '-u', default='Sai', help='User name for API credentials')
    parser.add_argument('--days', '-d', type=int, default=5, help='Lookback period in days (default: 5)')
    parser.add_argument('--test', action='store_true', help='Run in test mode (no Telegram)')
    args = parser.parse_args()

    checker = VSRAlertPerformanceChecker(
        user_name=args.user,
        lookback_days=args.days
    )

    if args.test:
        # Test mode - just identify candidates without sending
        strong_buys = checker.identify_strong_buys()
        print(f"\nFound {len(strong_buys)} STRONG BUY candidates:\n")
        for buy in strong_buys:
            print(f"  {buy['ticker']}: Alert ₹{buy['alerted_price']:.2f} -> "
                  f"Now ₹{buy['current_price']:.2f} (+{buy['gain_pct']:.1f}%)")
    else:
        checker.run()


if __name__ == "__main__":
    main()
