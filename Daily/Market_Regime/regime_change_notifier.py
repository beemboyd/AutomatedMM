#!/usr/bin/env python3
"""
Market Regime Change Notifier
Monitors regime changes and sends Telegram alerts
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from alerts.telegram_notifier import TelegramNotifier

class RegimeChangeNotifier:
    """Monitors and alerts on market regime changes"""
    
    def __init__(self):
        """Initialize the regime change notifier"""
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.script_dir, "data")
        self.regime_file = os.path.join(self.script_dir, "regime_analysis", "latest_regime_summary.json")
        self.state_file = os.path.join(self.data_dir, "regime_notifier_state.json")
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize Telegram notifier
        self.telegram = TelegramNotifier()
        
        # Load last known regime
        self.last_regime = self._load_last_regime()
        
        # Regime emojis for visual alerts
        self.regime_emojis = {
            'strong_uptrend': '🚀📈',
            'uptrend': '📈',
            'choppy_bullish': '📊➕',
            'choppy': '📊',
            'choppy_bearish': '📊➖',
            'downtrend': '📉',
            'strong_downtrend': '📉🔻'
        }
        
        # Regime colors for importance
        self.regime_importance = {
            'strong_uptrend': 'critical',
            'strong_downtrend': 'critical',
            'uptrend': 'high',
            'downtrend': 'high',
            'choppy_bullish': 'medium',
            'choppy_bearish': 'medium',
            'choppy': 'low'
        }
        
    def _load_last_regime(self):
        """Load the last known regime from state file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    return state.get('last_regime')
        except Exception as e:
            self.logger.error(f"Error loading state: {e}")
        return None
    
    def _save_last_regime(self, regime):
        """Save the current regime to state file"""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            state = {
                'last_regime': regime,
                'last_update': datetime.now().isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")
    
    def check_regime_change(self):
        """Check if market regime has changed and send alert if needed"""
        try:
            # Load current regime
            if not os.path.exists(self.regime_file):
                self.logger.warning(f"Regime file not found: {self.regime_file}")
                return False
            
            with open(self.regime_file, 'r') as f:
                current_data = json.load(f)
            
            current_regime = current_data['market_regime']['regime']
            
            # Check if regime has changed
            if self.last_regime is None:
                # First run, just save the regime
                self._save_last_regime(current_regime)
                self.logger.info(f"Initial regime set to: {current_regime}")
                return False
            
            if current_regime != self.last_regime:
                # Regime has changed!
                self._send_regime_change_alert(current_data, self.last_regime)
                self._save_last_regime(current_regime)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking regime change: {e}")
            return False
    
    def _send_regime_change_alert(self, current_data, previous_regime):
        """Send Telegram alert for regime change"""
        try:
            current_regime = current_data['market_regime']['regime']
            regime_info = current_data['market_regime']
            trend_analysis = current_data.get('trend_analysis', {})
            
            # Get emojis
            current_emoji = self.regime_emojis.get(current_regime, '📊')
            previous_emoji = self.regime_emojis.get(previous_regime, '📊')
            
            # Determine alert urgency
            importance = self.regime_importance.get(current_regime, 'medium')
            urgency_emoji = '🚨' if importance == 'critical' else '⚠️' if importance == 'high' else '📢'
            
            # Build message
            message = f"""{urgency_emoji} <b>Market Regime Change Detected</b>

{previous_emoji} {self._format_regime_name(previous_regime)}
    ⬇️
{current_emoji} <b>{self._format_regime_name(current_regime)}</b>

📊 <b>Current Market Conditions:</b>
• Confidence: {regime_info.get('confidence', 0):.1%}
• Long Reversals: {current_data.get('reversal_counts', {}).get('long', 0)}
• Short Reversals: {current_data.get('reversal_counts', {}).get('short', 0)}
• Market Score: {trend_analysis.get('market_score', 0):.2f}

📋 <b>Strategy:</b>
{regime_info.get('strategy', 'N/A')}

⏰ {datetime.now().strftime('%I:%M %p')}

<i>Dashboard: http://localhost:8080/</i>"""
            
            # Send notification
            if self.telegram.is_configured():
                self.telegram.send_message(message, parse_mode='HTML')
                self.logger.info(f"Sent regime change alert: {previous_regime} -> {current_regime}")
            else:
                self.logger.warning("Telegram not configured, cannot send alert")
                
        except Exception as e:
            self.logger.error(f"Error sending regime change alert: {e}")
    
    def _format_regime_name(self, regime):
        """Format regime name for display"""
        return regime.replace('_', ' ').title()
    
    def run_once(self):
        """Run a single check for regime change"""
        changed = self.check_regime_change()
        if changed:
            self.logger.info("Regime change detected and alert sent")
        else:
            self.logger.info("No regime change detected")
        return changed


def main():
    """Main function to test the notifier"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    notifier = RegimeChangeNotifier()
    notifier.run_once()


if __name__ == "__main__":
    main()