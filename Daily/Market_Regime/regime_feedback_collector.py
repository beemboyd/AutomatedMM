#!/usr/bin/env python3
"""
Regime Feedback Collector Service
Continuously collects feedback on predictions during market hours
Part of Phase 2: Restore Learning
"""

import os
import sys
import time
import sqlite3
import logging
from datetime import datetime, timedelta, time as datetime_time
import schedule

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from actual_regime_calculator import ActualRegimeCalculator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/maverick/PycharmProjects/India-TS/Daily/logs/regime_feedback_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RegimeFeedbackCollector:
    """Service to continuously collect regime feedback"""
    
    def __init__(self, user='Sai'):
        self.user = user
        self.calculator = ActualRegimeCalculator(user)
        self.is_running = False
        
        # Market hours (IST)
        self.market_open = datetime_time(9, 15)
        self.market_close = datetime_time(15, 30)
        
        # Processing parameters
        self.feedback_delay_minutes = 45  # Wait 45 minutes after prediction
        self.collection_interval_minutes = 5  # Check for new predictions every 5 minutes
        
        # Statistics
        self.stats = {
            'session_start': None,
            'predictions_processed': 0,
            'correct_predictions': 0,
            'regime_distribution': {}
        }
        
    def is_market_hours(self):
        """Check if current time is within market hours"""
        now = datetime.now().time()
        
        # Check if it's a weekday
        if datetime.now().weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
            
        return self.market_open <= now <= self.market_close
        
    def collect_feedback(self):
        """Collect feedback for recent predictions"""
        try:
            if not self.is_market_hours():
                logger.debug("Outside market hours, skipping feedback collection")
                return
                
            logger.info("Starting feedback collection cycle")
            
            # Process predictions from last 2 hours that are at least 45 minutes old
            processed = self.calculator.process_pending_predictions(
                lookback_hours=2, 
                delay_minutes=self.feedback_delay_minutes
            )
            
            if processed > 0:
                self.stats['predictions_processed'] += processed
                logger.info(f"Processed {processed} predictions in this cycle")
                
                # Update statistics
                self._update_statistics()
                
        except Exception as e:
            logger.error(f"Error in feedback collection: {str(e)}")
            
    def _update_statistics(self):
        """Update session statistics"""
        try:
            conn = sqlite3.connect(self.calculator.feedback_db_path)
            cursor = conn.cursor()
            
            # Get session statistics
            session_start = self.stats['session_start'].strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN predicted_regime = actual_regime THEN 1 ELSE 0 END) as correct,
                    actual_regime,
                    COUNT(*) as regime_count
                FROM regime_feedback
                WHERE feedback_timestamp > ?
                GROUP BY actual_regime
            ''', (session_start,))
            
            results = cursor.fetchall()
            
            if results:
                total = sum(r[3] for r in results)
                correct = sum(r[1] for r in results if r[1])
                
                # Update regime distribution
                for row in results:
                    regime = row[2]
                    count = row[3]
                    self.stats['regime_distribution'][regime] = count
                    
                if total > 0:
                    accuracy = (correct / total) * 100
                    logger.info(f"Session Stats - Accuracy: {accuracy:.2f}% ({correct}/{total})")
                    logger.info(f"Regime Distribution: {self.stats['regime_distribution']}")
                    
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating statistics: {str(e)}")
            
    def generate_report(self):
        """Generate daily feedback report"""
        try:
            logger.info("Generating daily feedback report")
            
            conn = sqlite3.connect(self.calculator.feedback_db_path)
            cursor = conn.cursor()
            
            # Get today's metrics
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute('''
                SELECT 
                    predicted_regime,
                    actual_regime,
                    COUNT(*) as count,
                    AVG(price_change_pct) as avg_price_change,
                    AVG(volatility) as avg_volatility
                FROM regime_feedback
                WHERE DATE(feedback_timestamp) = ?
                GROUP BY predicted_regime, actual_regime
                ORDER BY count DESC
            ''', (today,))
            
            confusion_matrix = cursor.fetchall()
            
            # Get overall accuracy
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN predicted_regime = actual_regime THEN 1 ELSE 0 END) as correct
                FROM regime_feedback
                WHERE DATE(feedback_timestamp) = ?
            ''', (today,))
            
            result = cursor.fetchone()
            
            report = {
                'date': today,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_validations': result[0] if result else 0,
                'correct_predictions': result[1] if result else 0,
                'accuracy_pct': (result[1] / result[0] * 100) if result and result[0] > 0 else 0,
                'confusion_matrix': confusion_matrix,
                'session_stats': self.stats
            }
            
            # Save report
            report_path = f'/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/feedback_reports/report_{today}.json'
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            
            import json
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
                
            logger.info(f"Report saved to {report_path}")
            
            # Log summary
            if result and result[0] > 0:
                logger.info(f"Daily Summary - Total: {result[0]}, Correct: {result[1]}, Accuracy: {report['accuracy_pct']:.2f}%")
                
            conn.close()
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            return None
            
    def run(self):
        """Main service loop"""
        logger.info("Starting Regime Feedback Collector Service")
        self.stats['session_start'] = datetime.now()
        self.is_running = True
        
        # Schedule feedback collection every 5 minutes
        schedule.every(self.collection_interval_minutes).minutes.do(self.collect_feedback)
        
        # Schedule daily report at 3:35 PM (after market close)
        schedule.every().day.at("15:35").do(self.generate_report)
        
        # Initial collection
        self.collect_feedback()
        
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds
                
        except KeyboardInterrupt:
            logger.info("Service stopped by user")
            self.stop()
            
    def stop(self):
        """Stop the service"""
        logger.info("Stopping Regime Feedback Collector Service")
        self.is_running = False
        
        # Generate final report
        self.generate_report()
        
        logger.info(f"Service stopped - Processed {self.stats['predictions_processed']} predictions")


def main():
    """Main entry point"""
    collector = RegimeFeedbackCollector(user='Sai')
    
    try:
        collector.run()
    except Exception as e:
        logger.error(f"Service error: {str(e)}")
        collector.stop()


if __name__ == "__main__":
    main()