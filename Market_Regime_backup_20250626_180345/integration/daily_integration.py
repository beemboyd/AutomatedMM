"""
Daily Trading System Integration

Integrates Market Regime detection with the Daily trading folder components.
"""

import sys
import os
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Market_Regime.core.regime_detector import RegimeDetector
from Market_Regime.actions.recommendation_engine import RecommendationEngine
from Market_Regime.learning.adaptive_learner import AdaptiveLearner


class DailyTradingIntegration:
    """Integrate market regime detection with Daily trading system"""
    
    def __init__(self, config_path: str = None):
        """Initialize integration"""
        self.logger = logging.getLogger(__name__)
        
        # Initialize regime components
        self.regime_detector = RegimeDetector(config_path)
        self.recommendation_engine = RecommendationEngine(config_path)
        self.adaptive_learner = AdaptiveLearner(config_path)
        
        # Daily folder paths
        self.daily_base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'Daily')
        self.scanner_results_path = os.path.join(self.daily_base, 'results')
        self.analysis_path = os.path.join(self.daily_base, 'analysis')
        self.current_orders_path = os.path.join(self.daily_base, 'Current_Orders')
        
        # Load configuration
        if config_path is None:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                     'config', 'regime_config.json')
        with open(config_path, 'r') as f:
            self.config = json.load(f)
    
    def analyze_current_market_regime(self) -> Dict[str, any]:
        """
        Analyze current market regime using available data
        
        Returns:
            Complete regime analysis with recommendations
        """
        try:
            # Get market data
            market_data = self._get_market_data()
            
            # Get scanner data
            scanner_data = self._get_latest_scanner_results()
            
            # Detect regime
            regime_analysis = self.regime_detector.detect_regime(market_data, scanner_data)
            
            # Get portfolio state
            portfolio_state = self._get_portfolio_state()
            
            # Generate recommendations
            recommendations = self.recommendation_engine.generate_recommendations(
                regime_analysis, portfolio_state
            )
            
            # Enhance with learning if available
            enhanced_regime, enhanced_confidence = self.adaptive_learner.get_enhanced_prediction(
                regime_analysis['indicators'],
                regime_analysis['regime'],
                regime_analysis['confidence']
            )
            
            # Update analysis with enhanced predictions
            regime_analysis['enhanced_regime'] = enhanced_regime
            regime_analysis['enhanced_confidence'] = enhanced_confidence
            
            # Record prediction for learning
            prediction_id = self.adaptive_learner.record_prediction(
                enhanced_regime,
                enhanced_confidence,
                regime_analysis['indicators'],
                regime_analysis['indicators'].get('market_score', 0)
            )
            
            # Combine all results
            full_analysis = {
                'regime_analysis': regime_analysis,
                'recommendations': recommendations,
                'prediction_id': prediction_id,
                'timestamp': datetime.now().isoformat()
            }
            
            # Save analysis
            self._save_analysis(full_analysis)
            
            return full_analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing market regime: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def update_trading_parameters(self, regime_analysis: Dict[str, any]) -> Dict[str, any]:
        """Update trading parameters based on regime"""
        updates = {}
        
        try:
            regime = regime_analysis['regime_analysis']['enhanced_regime']
            recommendations = regime_analysis['recommendations']
            
            # Position sizing updates
            position_sizing = recommendations['position_sizing']
            updates['position_size_multiplier'] = position_sizing['size_multiplier']
            updates['max_position_size'] = position_sizing['max_position_size']
            updates['concentration_limit'] = position_sizing['concentration_limit']
            
            # Risk management updates
            risk_mgmt = recommendations['risk_management']
            updates['stop_loss_multiplier'] = risk_mgmt['stop_loss_multiplier']
            updates['risk_per_trade'] = risk_mgmt['risk_per_trade']
            updates['max_portfolio_heat'] = risk_mgmt['portfolio_heat']
            
            # Capital deployment
            capital = recommendations['capital_deployment']
            updates['new_capital_deployment_rate'] = capital['deployment_rate']
            updates['target_cash_percentage'] = capital['cash_allocation']
            
            # Update config files
            self._update_config_files(updates)
            
            # Update watchdog parameters
            self._update_watchdog_parameters(updates, regime)
            
            return {
                'status': 'success',
                'updates_applied': updates,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error updating trading parameters: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def get_regime_aware_scan_filters(self) -> Dict[str, any]:
        """Get scan filters adjusted for current regime"""
        try:
            # Get current regime
            latest_analysis = self._load_latest_analysis()
            if not latest_analysis:
                return self._get_default_scan_filters()
            
            regime = latest_analysis['regime_analysis']['enhanced_regime']
            
            # Define regime-specific filters
            filters = {
                'strong_bull': {
                    'min_volume': 1000000,
                    'min_price': 50,
                    'max_price': 10000,
                    'min_rsi': 40,
                    'max_rsi': 80,
                    'trend_filter': 'uptrend',
                    'breakout_enabled': True,
                    'pullback_enabled': True
                },
                'bull': {
                    'min_volume': 500000,
                    'min_price': 50,
                    'max_price': 5000,
                    'min_rsi': 35,
                    'max_rsi': 75,
                    'trend_filter': 'uptrend',
                    'breakout_enabled': True,
                    'pullback_enabled': True
                },
                'neutral': {
                    'min_volume': 500000,
                    'min_price': 50,
                    'max_price': 5000,
                    'min_rsi': 30,
                    'max_rsi': 70,
                    'trend_filter': 'any',
                    'breakout_enabled': False,
                    'pullback_enabled': True
                },
                'bear': {
                    'min_volume': 1000000,
                    'min_price': 100,
                    'max_price': 5000,
                    'min_rsi': 20,
                    'max_rsi': 50,
                    'trend_filter': 'oversold_only',
                    'breakout_enabled': False,
                    'pullback_enabled': False
                },
                'volatile': {
                    'min_volume': 2000000,
                    'min_price': 100,
                    'max_price': 3000,
                    'min_rsi': 25,
                    'max_rsi': 75,
                    'trend_filter': 'range_bound',
                    'breakout_enabled': False,
                    'pullback_enabled': True
                },
                'crisis': {
                    'min_volume': 5000000,
                    'min_price': 200,
                    'max_price': 2000,
                    'min_rsi': 10,
                    'max_rsi': 40,
                    'trend_filter': 'defensive_only',
                    'breakout_enabled': False,
                    'pullback_enabled': False
                }
            }
            
            # Get regime-specific filters
            regime_filters = filters.get(regime, filters['neutral'])
            
            # Add sector preferences
            sector_prefs = latest_analysis['recommendations']['sector_preferences']
            regime_filters['preferred_sectors'] = sector_prefs['preferred_sectors']
            regime_filters['avoid_sectors'] = sector_prefs['avoid_sectors']
            
            return regime_filters
            
        except Exception as e:
            self.logger.error(f"Error getting scan filters: {e}")
            return self._get_default_scan_filters()
    
    def should_place_order(self, ticker: str, signal: Dict[str, any]) -> Tuple[bool, str]:
        """
        Check if order should be placed based on regime
        
        Returns:
            Tuple of (should_place, reason)
        """
        try:
            # Get current regime
            latest_analysis = self._load_latest_analysis()
            if not latest_analysis:
                return True, "No regime data - proceeding with default"
            
            regime = latest_analysis['regime_analysis']['enhanced_regime']
            confidence = latest_analysis['regime_analysis']['enhanced_confidence']
            
            # Crisis mode - no new orders
            if regime == 'crisis':
                return False, "Crisis regime - no new positions"
            
            # Low confidence - be cautious
            if confidence < 0.4:
                return False, f"Low regime confidence: {confidence:.1%}"
            
            # Check capital deployment rate
            deployment_rate = latest_analysis['recommendations']['capital_deployment']['deployment_rate']
            if deployment_rate == 0:
                return False, f"Zero capital deployment in {regime} regime"
            
            # Check sector if available
            if 'sector' in signal:
                avoid_sectors = latest_analysis['recommendations']['sector_preferences']['avoid_sectors']
                if signal['sector'] in avoid_sectors:
                    return False, f"Sector {signal['sector']} not recommended in {regime} regime"
            
            # Check signal strength vs regime
            if 'strength' in signal:
                min_strength = {
                    'strong_bull': 0.5,
                    'bull': 0.6,
                    'neutral': 0.7,
                    'bear': 0.8,
                    'strong_bear': 0.9,
                    'volatile': 0.75
                }
                
                required_strength = min_strength.get(regime, 0.7)
                if signal['strength'] < required_strength:
                    return False, f"Signal strength {signal['strength']:.2f} below {required_strength:.2f} required for {regime}"
            
            return True, f"Order approved for {regime} regime"
            
        except Exception as e:
            self.logger.error(f"Error checking order placement: {e}")
            return True, "Error in regime check - proceeding with caution"
    
    def get_position_size_multiplier(self, ticker: str, base_size: float) -> float:
        """Get position size multiplier based on regime"""
        try:
            latest_analysis = self._load_latest_analysis()
            if not latest_analysis:
                return 1.0
            
            return latest_analysis['recommendations']['position_sizing']['size_multiplier']
            
        except Exception as e:
            self.logger.error(f"Error getting position size multiplier: {e}")
            return 0.8  # Conservative default
    
    def get_stop_loss_adjustment(self, ticker: str, base_stop: float) -> float:
        """Get stop loss adjustment based on regime"""
        try:
            latest_analysis = self._load_latest_analysis()
            if not latest_analysis:
                return 1.0
            
            return latest_analysis['recommendations']['risk_management']['stop_loss_multiplier']
            
        except Exception as e:
            self.logger.error(f"Error getting stop loss adjustment: {e}")
            return 0.8  # Tighter default
    
    # Private helper methods
    def _get_market_data(self) -> pd.DataFrame:
        """Get market data for regime detection"""
        # For now, create sample data
        # In production, this would fetch from Kite or market data provider
        
        # Try to load from a market data file if available
        market_data_file = os.path.join(self.daily_base, 'data', 'market_data.csv')
        
        if os.path.exists(market_data_file):
            return pd.read_csv(market_data_file, index_col=0, parse_dates=True)
        
        # Generate sample data
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
        
        data = pd.DataFrame({
            'date': dates,
            'open': np.random.randn(100).cumsum() + 15000,
            'high': np.random.randn(100).cumsum() + 15100,
            'low': np.random.randn(100).cumsum() + 14900,
            'close': np.random.randn(100).cumsum() + 15000,
            'volume': np.random.randint(1000000, 5000000, 100)
        })
        
        data.set_index('date', inplace=True)
        return data
    
    def _get_latest_scanner_results(self) -> Optional[pd.DataFrame]:
        """Get latest scanner results from multiple sources"""
        try:
            # Collect all scanner dataframes
            all_dfs = []
            
            # 1. Primary source: Long Reversal Daily from Market_Regime/results first, then Daily/results
            market_regime_results = os.path.join(self.daily_base, 'Market_Regime', 'results')
            long_results_path = os.path.join(self.daily_base, 'results')
            
            # Check Market_Regime/results first for the latest data
            if os.path.exists(market_regime_results):
                long_files = [f for f in os.listdir(market_regime_results) 
                             if f.startswith('Long_Reversal_Daily_') and f.endswith('.xlsx')]
                if long_files:
                    long_files.sort()
                    latest_long = long_files[-1]
                    file_path = os.path.join(market_regime_results, latest_long)
                    try:
                        df = pd.read_excel(file_path)
                        df['Direction'] = 'LONG'
                        df['signal'] = 'BUY'
                        all_dfs.append(df)
                        self.logger.info(f"Loaded {len(df)} LONG signals from {latest_long}")
                    except Exception as e:
                        self.logger.warning(f"Could not load {latest_long}: {e}")
            
            # Fallback to Daily/results if not found in Market_Regime/results
            if not all_dfs and os.path.exists(long_results_path):
                long_files = [f for f in os.listdir(long_results_path) 
                             if f.startswith('Long_Reversal_Daily_') and f.endswith('.xlsx')]
                if long_files:
                    long_files.sort()
                    latest_long = long_files[-1]
                    file_path = os.path.join(long_results_path, latest_long)
                    try:
                        df = pd.read_excel(file_path)
                        df['Direction'] = 'LONG'
                        df['signal'] = 'BUY'
                        all_dfs.append(df)
                        self.logger.info(f"Loaded {len(df)} LONG signals from fallback: {latest_long}")
                    except Exception as e:
                        self.logger.warning(f"Could not load fallback {latest_long}: {e}")
            
            # 2. Primary source: Short Reversal Daily from Market_Regime/results first
            short_results_path = os.path.join(self.daily_base, 'results-s')
            if os.path.exists(market_regime_results):
                short_files = [f for f in os.listdir(market_regime_results) 
                              if f.startswith('Short_Reversal_Daily_') and f.endswith('.xlsx')]
                if short_files:
                    short_files.sort()
                    latest_short = short_files[-1]
                    file_path = os.path.join(market_regime_results, latest_short)
                    try:
                        df = pd.read_excel(file_path)
                        df['Direction'] = 'SHORT'
                        df['signal'] = 'SELL'
                        all_dfs.append(df)
                        self.logger.info(f"Loaded {len(df)} SHORT signals from {latest_short}")
                    except Exception as e:
                        self.logger.warning(f"Could not load {latest_short}: {e}")
            
            # Fallback to Daily/results-s if not found in Market_Regime/results
            if len([df for df in all_dfs if 'Direction' in df.columns and (df['Direction'] == 'SHORT').any()]) == 0:
                if os.path.exists(short_results_path):
                    short_files = [f for f in os.listdir(short_results_path) 
                                  if f.startswith('Short_Reversal_Daily_') and f.endswith('.xlsx')]
                    if short_files:
                        short_files.sort()
                        latest_short = short_files[-1]
                        file_path = os.path.join(short_results_path, latest_short)
                        try:
                            df = pd.read_excel(file_path)
                            df['Direction'] = 'SHORT'
                            df['signal'] = 'SELL'
                            all_dfs.append(df)
                            self.logger.info(f"Loaded {len(df)} SHORT signals from fallback: {latest_short}")
                        except Exception as e:
                            self.logger.warning(f"Could not load fallback {latest_short}: {e}")
            
            # 3. Fallback: Check Market_Regime/results if main sources not found
            if not all_dfs:
                daily_regime_path = os.path.join(self.daily_base, 'Market_Regime', 'results')
                if os.path.exists(daily_regime_path):
                    for pattern in ['Long_Reversal_Daily_', 'Short_Reversal_Daily_']:
                        files = [f for f in os.listdir(daily_regime_path) 
                                if f.startswith(pattern) and f.endswith('.xlsx')]
                        if files:
                            files.sort()
                            latest_file = files[-1]
                            file_path = os.path.join(daily_regime_path, latest_file)
                            try:
                                df = pd.read_excel(file_path)
                                if 'Long_Reversal' in pattern:
                                    df['Direction'] = 'LONG'
                                    df['signal'] = 'BUY'
                                else:
                                    df['Direction'] = 'SHORT'
                                    df['signal'] = 'SELL'
                                all_dfs.append(df)
                                self.logger.info(f"Loaded {len(df)} rows from fallback: {latest_file}")
                            except Exception as e:
                                self.logger.warning(f"Could not load {latest_file}: {e}")
            
            if not all_dfs:
                self.logger.warning("No scanner results found")
                return None
            
            # Combine all dataframes
            combined_df = pd.concat(all_dfs, ignore_index=True)
            
            # Remove duplicates based on Ticker
            if 'Ticker' in combined_df.columns:
                combined_df = combined_df.drop_duplicates(subset=['Ticker'], keep='first')
            
            # Add required columns if missing
            if 'strength' not in combined_df.columns and 'Score' in combined_df.columns:
                try:
                    combined_df['Score'] = pd.to_numeric(combined_df['Score'], errors='coerce')
                    combined_df['Score'] = combined_df['Score'].fillna(50)
                    combined_df['strength'] = combined_df['Score'] / 100.0
                except Exception as e:
                    self.logger.warning(f"Could not convert Score to strength: {e}")
                    combined_df['strength'] = 0.5
            
            self.logger.info(f"Combined scanner results: {len(combined_df)} unique tickers")
            return combined_df
            
        except Exception as e:
            self.logger.error(f"Error loading scanner results: {e}")
            return None
    
    def _get_portfolio_state(self) -> Dict[str, any]:
        """Get current portfolio state"""
        portfolio_state = {
            'total_capital': 1000000,  # Default
            'deployed_capital': 0,
            'cash': 1000000,
            'positions': [],
            'total_exposure': 0,
            'cash_percentage': 1.0
        }
        
        try:
            # Get all user positions
            total_value = 0
            all_positions = []
            
            for user_dir in os.listdir(self.current_orders_path):
                user_path = os.path.join(self.current_orders_path, user_dir)
                if not os.path.isdir(user_path):
                    continue
                
                # Find active order files
                for file in os.listdir(user_path):
                    if file.startswith('orders_') and file.endswith('.json') and '_closed' not in file:
                        order_file = os.path.join(user_path, file)
                        
                        with open(order_file, 'r') as f:
                            orders = json.load(f)
                        
                        if 'orders' in orders:
                            for order in orders['orders']:
                                if order.get('status') in ['OPEN', 'COMPLETE']:
                                    position_value = order.get('quantity', 0) * order.get('average_price', 0)
                                    total_value += position_value
                                    
                                    all_positions.append({
                                        'symbol': order.get('symbol'),
                                        'quantity': order.get('quantity'),
                                        'value': position_value,
                                        'allocation': 0  # Will calculate after
                                    })
            
            # Update portfolio state
            if total_value > 0:
                portfolio_state['deployed_capital'] = total_value
                portfolio_state['cash'] = portfolio_state['total_capital'] - total_value
                portfolio_state['total_exposure'] = total_value / portfolio_state['total_capital']
                portfolio_state['cash_percentage'] = portfolio_state['cash'] / portfolio_state['total_capital']
                
                # Calculate allocations
                for pos in all_positions:
                    pos['allocation'] = pos['value'] / portfolio_state['total_capital']
                
                portfolio_state['positions'] = all_positions
            
        except Exception as e:
            self.logger.error(f"Error getting portfolio state: {e}")
        
        return portfolio_state
    
    def _save_analysis(self, analysis: Dict[str, any]):
        """Save regime analysis"""
        try:
            # Create reports directory
            reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports')
            os.makedirs(reports_dir, exist_ok=True)
            
            # Save with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'regime_analysis_{timestamp}.json'
            filepath = os.path.join(reports_dir, filename)
            
            with open(filepath, 'w') as f:
                json.dump(analysis, f, indent=2)
            
            # Also save as latest
            latest_path = os.path.join(reports_dir, 'regime_analysis_latest.json')
            with open(latest_path, 'w') as f:
                json.dump(analysis, f, indent=2)
            
            self.logger.info(f"Regime analysis saved to {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error saving analysis: {e}")
    
    def _load_latest_analysis(self) -> Optional[Dict[str, any]]:
        """Load most recent regime analysis"""
        try:
            reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports')
            latest_path = os.path.join(reports_dir, 'regime_analysis_latest.json')
            
            if os.path.exists(latest_path):
                with open(latest_path, 'r') as f:
                    return json.load(f)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error loading latest analysis: {e}")
            return None
    
    def _get_default_scan_filters(self) -> Dict[str, any]:
        """Get default scan filters"""
        return {
            'min_volume': 1000000,
            'min_price': 50,
            'max_price': 5000,
            'min_rsi': 30,
            'max_rsi': 70,
            'trend_filter': 'any',
            'breakout_enabled': True,
            'pullback_enabled': True,
            'preferred_sectors': [],
            'avoid_sectors': []
        }
    
    def _update_config_files(self, updates: Dict[str, any]):
        """Update configuration files with new parameters"""
        try:
            # Update main config.ini
            config_path = os.path.join(self.daily_base, 'config.ini')
            
            if os.path.exists(config_path):
                # Read existing config
                import configparser
                config = configparser.ConfigParser()
                config.read(config_path)
                
                # Update regime section
                if 'REGIME' not in config:
                    config['REGIME'] = {}
                
                for key, value in updates.items():
                    config['REGIME'][key] = str(value)
                
                # Write back
                with open(config_path, 'w') as f:
                    config.write(f)
                
                self.logger.info("Updated config.ini with regime parameters")
                
        except Exception as e:
            self.logger.error(f"Error updating config files: {e}")
    
    def _update_watchdog_parameters(self, updates: Dict[str, any], regime: str):
        """Update watchdog parameters based on regime"""
        try:
            # Create a watchdog config update file
            watchdog_config = {
                'regime': regime,
                'stop_loss_multiplier': updates.get('stop_loss_multiplier', 1.0),
                'risk_per_trade': updates.get('risk_per_trade', 0.01),
                'trailing_stop_enabled': regime in ['strong_bull', 'bull'],
                'timestamp': datetime.now().isoformat()
            }
            
            # Save to a file that watchdog can read
            watchdog_config_path = os.path.join(self.daily_base, 'regime_watchdog_config.json')
            with open(watchdog_config_path, 'w') as f:
                json.dump(watchdog_config, f, indent=2)
            
            self.logger.info("Updated watchdog parameters for regime: %s", regime)
            
        except Exception as e:
            self.logger.error(f"Error updating watchdog parameters: {e}")


# Convenience function for command-line usage
def analyze_and_update():
    """Run regime analysis and update trading parameters"""
    integration = DailyTradingIntegration()
    
    # Analyze current regime
    analysis = integration.analyze_current_market_regime()
    
    if 'error' not in analysis:
        # Update trading parameters
        updates = integration.update_trading_parameters(analysis)
        
        # Print summary
        print(f"Regime: {analysis['regime_analysis']['enhanced_regime']}")
        print(f"Confidence: {analysis['regime_analysis']['enhanced_confidence']:.1%}")
        print(f"Recommendations: {analysis['recommendations']['specific_actions']}")
        
        return analysis
    else:
        print(f"Error: {analysis['error']}")
        return None


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Run analysis
    analyze_and_update()