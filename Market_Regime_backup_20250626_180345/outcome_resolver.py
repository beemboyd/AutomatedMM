#!/usr/bin/env python3
"""
Outcome Resolver for Market Regime Predictions
Resolves predictions made 30 minutes ago by comparing with actual market behavior
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.market_indicators import MarketIndicators
from core.regime_detector import RegimeDetector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OutcomeResolver:
    """Resolves pending predictions by calculating actual market regime"""
    
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), 'data', 'regime_learning.db')
        self.indicators = MarketIndicators()
        self.detector = RegimeDetector()
        
        # Import data handler for market data
        import sys
        import configparser
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        
        # Load config from Daily folder with user credentials
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                  'Daily', 'config.ini')
        if os.path.exists(config_path):
            config = configparser.ConfigParser()
            config.read(config_path)
            
            # Use default user "Sai"
            user_name = "Sai"
            credential_section = f'API_CREDENTIALS_{user_name}'
            
            if credential_section in config.sections():
                # Set environment variables for data handler
                os.environ['ZERODHA_API_KEY'] = config.get(credential_section, 'api_key')
                os.environ['ZERODHA_ACCESS_TOKEN'] = config.get(credential_section, 'access_token')
                logger.info(f"Loaded credentials for user {user_name}")
        
        from data_handler import DataHandler
        self.data_handler = DataHandler()
        
    def get_pending_predictions(self, timeframe_minutes: int = 30) -> pd.DataFrame:
        """Get predictions that are ready to be resolved"""
        conn = sqlite3.connect(self.db_path)
        
        # Get predictions that are at least timeframe_minutes old and unresolved
        cutoff_time = datetime.now() - timedelta(minutes=timeframe_minutes)
        
        query = """
        SELECT id, timestamp, predicted_regime, confidence, market_score, indicators
        FROM regime_predictions 
        WHERE (actual_regime IS NULL OR actual_regime = '')
        AND timestamp <= ?
        ORDER BY timestamp DESC
        LIMIT 100
        """
        
        df = pd.read_sql_query(query, conn, params=(cutoff_time.isoformat(),))
        conn.close()
        
        logger.info(f"Found {len(df)} predictions ready to resolve")
        return df
    
    def calculate_actual_regime(self, prediction_time: datetime, timeframe_minutes: int = 30) -> Tuple[str, Dict]:
        """Calculate what the actual regime was for the given timeframe"""
        try:
            # Get market data for the prediction period
            start_time = prediction_time
            end_time = prediction_time + timedelta(minutes=timeframe_minutes)
            
            # Get NIFTY data using data handler
            # Fetch intraday data for the period
            try:
                nifty_data = self.data_handler.fetch_historical_data(
                    ticker='NIFTY 50',
                    interval='minute',
                    from_date=start_time.strftime('%Y-%m-%d'),
                    to_date=end_time.strftime('%Y-%m-%d')
                )
                
                # Filter data to the specific time window
                if nifty_data is not None and not nifty_data.empty:
                    nifty_data['datetime'] = pd.to_datetime(nifty_data['date'])
                    mask = (nifty_data['datetime'] >= start_time) & (nifty_data['datetime'] <= end_time)
                    nifty_data = nifty_data[mask]
                
                if nifty_data is None or len(nifty_data) < 5:  # Need at least 5 minutes of data
                    logger.warning(f"Insufficient data for period {start_time} to {end_time}")
                    return None, {}
                    
            except Exception as e:
                logger.error(f"Error fetching NIFTY data: {e}")
                return None, {}
            
            # Calculate indicators for the period
            indicators = self.indicators.calculate_all_indicators(nifty_data)
            
            # Key metrics for regime determination
            price_change = (nifty_data['close'].iloc[-1] - nifty_data['close'].iloc[0]) / nifty_data['close'].iloc[0]
            volatility = nifty_data['close'].pct_change().std() * np.sqrt(252 * 13)  # Annualized
            volume_ratio = nifty_data['volume'].mean() / nifty_data['volume'].rolling(20).mean().iloc[-1]
            
            # Determine actual regime based on 30-min performance
            actual_regime = self._determine_short_term_regime(
                price_change, volatility, volume_ratio, indicators
            )
            
            metrics = {
                'price_change': price_change,
                'volatility': volatility,
                'volume_ratio': volume_ratio,
                'high': nifty_data['high'].max(),
                'low': nifty_data['low'].min(),
                'close': nifty_data['close'].iloc[-1]
            }
            
            return actual_regime, metrics
            
        except Exception as e:
            logger.error(f"Error calculating actual regime: {e}")
            return None, {}
    
    def _determine_short_term_regime(self, price_change: float, volatility: float, 
                                   volume_ratio: float, indicators: Dict) -> str:
        """Determine regime based on 30-minute market behavior"""
        
        # Short-term regime thresholds (30-min)
        PRICE_CHANGE_STRONG = 0.005  # 0.5% in 30 min is significant
        PRICE_CHANGE_MODERATE = 0.002  # 0.2%
        VOLATILITY_HIGH = 0.02  # 2% volatility is high for 30 min
        VOLATILITY_CRISIS = 0.04  # 4% is crisis level
        
        # Crisis detection first
        if volatility > VOLATILITY_CRISIS:
            return 'crisis'
        
        # High volatility
        if volatility > VOLATILITY_HIGH:
            if abs(price_change) < PRICE_CHANGE_MODERATE:
                return 'volatile'
            elif price_change > 0:
                return 'volatile_bullish'
            else:
                return 'volatile_bearish'
        
        # Trend detection
        if price_change > PRICE_CHANGE_STRONG:
            if volume_ratio > 1.2:
                return 'strong_uptrend'
            else:
                return 'uptrend'
        elif price_change < -PRICE_CHANGE_STRONG:
            if volume_ratio > 1.2:
                return 'strong_downtrend'
            else:
                return 'downtrend'
        elif abs(price_change) < PRICE_CHANGE_MODERATE:
            return 'neutral'
        else:
            # Moderate moves
            if price_change > 0:
                return 'bullish'
            else:
                return 'bearish'
    
    def calculate_outcome_score(self, predicted: str, actual: str) -> float:
        """Calculate how accurate the prediction was (0-1 scale)"""
        
        # Exact match
        if predicted == actual:
            return 1.0
        
        # Partial credit matrix
        partial_credit = {
            # Predicted -> Actual
            ('strong_uptrend', 'uptrend'): 0.8,
            ('strong_uptrend', 'bullish'): 0.7,
            ('uptrend', 'strong_uptrend'): 0.8,
            ('uptrend', 'bullish'): 0.8,
            ('uptrend', 'neutral'): 0.5,
            
            ('strong_downtrend', 'downtrend'): 0.8,
            ('strong_downtrend', 'bearish'): 0.7,
            ('downtrend', 'strong_downtrend'): 0.8,
            ('downtrend', 'bearish'): 0.8,
            ('downtrend', 'neutral'): 0.5,
            
            ('bullish', 'uptrend'): 0.8,
            ('bullish', 'neutral'): 0.6,
            ('bearish', 'downtrend'): 0.8,
            ('bearish', 'neutral'): 0.6,
            
            ('neutral', 'bullish'): 0.6,
            ('neutral', 'bearish'): 0.6,
            ('neutral', 'choppy'): 0.8,
            ('choppy', 'neutral'): 0.8,
            
            ('volatile', 'volatile_bullish'): 0.8,
            ('volatile', 'volatile_bearish'): 0.8,
            ('volatile', 'choppy'): 0.7,
            
            # Add more partial credit rules as needed
        }
        
        # Check for partial credit
        key = (predicted, actual)
        if key in partial_credit:
            return partial_credit[key]
        
        # Reverse key check
        reverse_key = (actual, predicted)
        if reverse_key in partial_credit:
            return partial_credit[reverse_key] * 0.9  # Slightly lower for reverse
        
        # No credit for completely wrong predictions
        return 0.0
    
    def update_prediction_outcome(self, prediction_id: int, actual_regime: str, 
                                outcome_score: float, metrics: Dict):
        """Update the database with the actual outcome"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE regime_predictions
                SET actual_regime = ?,
                    outcome_score = ?,
                    feedback_timestamp = ?
                WHERE id = ?
            """, (actual_regime, outcome_score, datetime.now().isoformat(), prediction_id))
            
            conn.commit()
            logger.info(f"Updated prediction {prediction_id}: predicted vs actual = {actual_regime}, score = {outcome_score:.2f}")
            
        except Exception as e:
            logger.error(f"Error updating prediction outcome: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def resolve_pending_predictions(self, timeframe_minutes: int = 30):
        """Main method to resolve all pending predictions"""
        logger.info(f"Starting outcome resolution for {timeframe_minutes}-minute predictions...")
        
        # Get pending predictions
        pending = self.get_pending_predictions(timeframe_minutes)
        
        if pending.empty:
            logger.info("No pending predictions to resolve")
            return
        
        resolved_count = 0
        total_score = 0
        
        for idx, row in pending.iterrows():
            prediction_time = pd.to_datetime(row['timestamp'])
            
            # Skip if outside market hours
            if prediction_time.hour < 9 or prediction_time.hour >= 16:
                logger.debug(f"Skipping prediction outside market hours: {prediction_time}")
                continue
            
            # Calculate actual regime
            actual_regime, metrics = self.calculate_actual_regime(prediction_time, timeframe_minutes)
            
            if actual_regime is None:
                continue
            
            # Calculate outcome score
            outcome_score = self.calculate_outcome_score(row['predicted_regime'], actual_regime)
            total_score += outcome_score
            
            # Update database
            self.update_prediction_outcome(row['id'], actual_regime, outcome_score, metrics)
            resolved_count += 1
            
            # Log performance
            if outcome_score >= 0.8:
                logger.info(f"✓ Good prediction: {row['predicted_regime']} → {actual_regime} (score: {outcome_score:.2f})")
            elif outcome_score >= 0.5:
                logger.info(f"~ Partial credit: {row['predicted_regime']} → {actual_regime} (score: {outcome_score:.2f})")
            else:
                logger.info(f"✗ Wrong prediction: {row['predicted_regime']} → {actual_regime} (score: {outcome_score:.2f})")
        
        # Summary
        if resolved_count > 0:
            avg_score = total_score / resolved_count
            logger.info(f"\nResolved {resolved_count} predictions")
            logger.info(f"Average accuracy score: {avg_score:.2%}")
            
            # Update model performance metrics
            self._update_performance_metrics(resolved_count, avg_score)
    
    def _update_performance_metrics(self, resolved_count: int, avg_score: float):
        """Update overall performance metrics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get last 100 resolved predictions for performance calculation
        cursor.execute("""
            SELECT predicted_regime, actual_regime, outcome_score
            FROM regime_predictions
            WHERE actual_regime IS NOT NULL AND actual_regime != ''
            ORDER BY feedback_timestamp DESC
            LIMIT 100
        """)
        
        results = cursor.fetchall()
        
        if results:
            # Calculate metrics
            total_accuracy = sum(r[2] for r in results) / len(results)
            exact_matches = sum(1 for r in results if r[0] == r[1])
            exact_accuracy = exact_matches / len(results)
            
            logger.info(f"\nPerformance Metrics (last 100 predictions):")
            logger.info(f"  Overall Accuracy: {total_accuracy:.2%}")
            logger.info(f"  Exact Match Rate: {exact_accuracy:.2%}")
            
            # Regime-specific accuracy
            regime_performance = {}
            for predicted, actual, score in results:
                if predicted not in regime_performance:
                    regime_performance[predicted] = {'correct': 0, 'total': 0, 'score_sum': 0}
                
                regime_performance[predicted]['total'] += 1
                regime_performance[predicted]['score_sum'] += score
                if predicted == actual:
                    regime_performance[predicted]['correct'] += 1
            
            logger.info("\n  Regime-Specific Performance:")
            for regime, stats in regime_performance.items():
                accuracy = stats['correct'] / stats['total']
                avg_score = stats['score_sum'] / stats['total']
                logger.info(f"    {regime}: {accuracy:.2%} exact, {avg_score:.2%} avg score ({stats['total']} predictions)")
        
        conn.close()


def main():
    """Run outcome resolution"""
    resolver = OutcomeResolver()
    
    # Resolve 30-minute predictions
    resolver.resolve_pending_predictions(timeframe_minutes=30)
    
    # Show current performance
    logger.info("\n" + "="*60)
    logger.info("Outcome resolution completed")
    logger.info("="*60)


if __name__ == "__main__":
    main()