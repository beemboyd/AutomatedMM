#!/usr/bin/env python3
"""
Daily Market Regime Analysis Script

This script runs daily to:
1. Detect market regimes for indices and portfolio stocks
2. Generate position sizing recommendations
3. Update stop loss recommendations
4. Create actionable reports for trading decisions
"""

import os
import sys
import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime, timedelta
import argparse
from typing import Dict, List, Optional

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from ML-Framework directory
from models.market_regime_ml import MarketRegimeML

# Try to import from parent directory, with fallback
try:
    from data_handler import DataHandler
    from state_manager import StateManager
except ImportError:
    # Create minimal implementations if main modules not available
    class DataHandler:
        def __init__(self):
            pass
    
    class StateManager:
        def __init__(self):
            pass
        
        def load_state(self):
            # Try to load from trading_state.json
            state_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'data', 'trading_state.json'
            )
            if os.path.exists(state_path):
                with open(state_path, 'r') as f:
                    return json.load(f)
            return {'positions': {}}
        
        def save_state(self, state):
            state_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'data', 'trading_state.json'
            )
            with open(state_path, 'w') as f:
                json.dump(state, f, indent=2)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'regime_analysis_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DailyRegimeAnalyzer:
    """
    Daily market regime analysis and recommendation generator.
    """
    
    def __init__(self, config_path=None):
        """Initialize the daily analyzer"""
        self.regime_detector = MarketRegimeML(config_path)
        self.data_handler = DataHandler()
        self.state_manager = StateManager()
        
        # Market indices
        self.indices = ['SMALLCAP', 'MIDCAP', 'TOP100CASE']
        
        # Output paths
        self.output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'results',
            'daily_analysis'
        )
        os.makedirs(self.output_dir, exist_ok=True)
        
    def run_daily_analysis(self):
        """Run complete daily market regime analysis"""
        logger.info("Starting daily market regime analysis...")
        
        try:
            # 1. Analyze market indices
            index_regimes = self._analyze_indices()
            
            # 2. Get portfolio positions
            positions = self._get_portfolio_positions()
            
            # 3. Analyze individual stocks
            stock_analysis = self._analyze_stocks(positions)
            
            # 4. Generate recommendations
            recommendations = self._generate_recommendations(
                index_regimes, 
                stock_analysis, 
                positions
            )
            
            # 5. Create reports
            self._create_reports(index_regimes, stock_analysis, recommendations)
            
            # 6. Update state with regime information
            self._update_state(stock_analysis, recommendations)
            
            logger.info("Daily analysis completed successfully")
            
            return {
                'status': 'success',
                'index_regimes': index_regimes,
                'stock_analysis': stock_analysis,
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Error in daily analysis: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _analyze_indices(self) -> Dict:
        """Analyze market indices for regime detection"""
        logger.info("Analyzing market indices...")
        
        index_regimes = {}
        
        for index in self.indices:
            try:
                # Load index data
                data = self._load_data(index)
                if data is None:
                    logger.warning(f"No data available for {index}")
                    continue
                
                # Detect regime
                regime, details = self.regime_detector.detect_regime(index, data)
                
                index_regimes[index] = {
                    'regime': regime,
                    'confidence': details['confidence'],
                    'metrics': details['metrics'],
                    'timestamp': datetime.now().isoformat()
                }
                
                logger.info(f"{index}: {regime} (confidence: {details['confidence']:.2f})")
                
            except Exception as e:
                logger.error(f"Error analyzing {index}: {str(e)}")
        
        return index_regimes
    
    def _get_portfolio_positions(self) -> Dict:
        """Get current portfolio positions from state"""
        try:
            state = self.state_manager.load_state()
            positions = state.get('positions', {})
            
            logger.info(f"Loaded {len(positions)} positions from state")
            return positions
            
        except Exception as e:
            logger.error(f"Error loading positions: {str(e)}")
            return {}
    
    def _analyze_stocks(self, positions: Dict) -> Dict:
        """Analyze individual stocks in portfolio and watchlist"""
        logger.info("Analyzing individual stocks...")
        
        stock_analysis = {}
        
        # Analyze portfolio positions
        for ticker in positions.keys():
            analysis = self._analyze_single_stock(ticker)
            if analysis:
                stock_analysis[ticker] = analysis
        
        # Analyze additional watchlist stocks
        watchlist = self._get_watchlist()
        for ticker in watchlist:
            if ticker not in stock_analysis:
                analysis = self._analyze_single_stock(ticker)
                if analysis:
                    stock_analysis[ticker] = analysis
        
        return stock_analysis
    
    def _analyze_single_stock(self, ticker: str):
        """Analyze a single stock"""
        try:
            # Load stock data
            data = self._load_data(ticker)
            if data is None:
                return None
            
            # Detect regime
            regime, details = self.regime_detector.detect_regime(ticker, data)
            
            # Determine reference index
            reference_index = self._get_reference_index(ticker)
            
            return {
                'ticker': ticker,
                'regime': regime,
                'confidence': details['confidence'],
                'metrics': details['metrics'],
                'position_adjustment': details['position_adjustment'],
                'stop_loss_multipliers': details['stop_loss_multipliers'],
                'reference_index': reference_index,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {str(e)}")
            return None
    
    def _generate_recommendations(self, index_regimes: Dict, 
                                stock_analysis: Dict, 
                                positions: Dict) -> Dict:
        """Generate trading recommendations based on regime analysis"""
        logger.info("Generating recommendations...")
        
        recommendations = {
            'market_outlook': self._get_market_outlook(index_regimes),
            'position_recommendations': {},
            'new_opportunities': [],
            'risk_alerts': [],
            'timestamp': datetime.now().isoformat()
        }
        
        # Generate recommendations for existing positions
        for ticker, position in positions.items():
            if ticker in stock_analysis:
                rec = self.regime_detector.get_position_recommendations(
                    ticker, 
                    {ticker: position}
                )
                recommendations['position_recommendations'][ticker] = rec
                
                # Check for risk alerts
                if rec.get('urgency') == 'HIGH':
                    recommendations['risk_alerts'].append({
                        'ticker': ticker,
                        'alert': rec.get('reason', ''),
                        'action': rec.get('position_action', '')
                    })
        
        # Identify new opportunities
        for ticker, analysis in stock_analysis.items():
            if ticker not in positions:
                if analysis['regime'] in ['STRONG_BULLISH', 'WEAK_BULLISH']:
                    if analysis['confidence'] > 0.7:
                        recommendations['new_opportunities'].append({
                            'ticker': ticker,
                            'regime': analysis['regime'],
                            'confidence': analysis['confidence'],
                            'position_size_factor': analysis['position_adjustment']
                        })
        
        return recommendations
    
    def _get_market_outlook(self, index_regimes: Dict) -> Dict:
        """Generate overall market outlook based on index regimes"""
        if not index_regimes:
            return {'outlook': 'UNKNOWN', 'confidence': 0}
        
        # Count regime types
        regime_counts = {}
        total_confidence = 0
        
        for index, data in index_regimes.items():
            regime = data['regime']
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
            total_confidence += data['confidence']
        
        # Determine dominant regime
        dominant_regime = max(regime_counts.items(), key=lambda x: x[1])[0]
        avg_confidence = total_confidence / len(index_regimes)
        
        # Map to market outlook
        outlook_map = {
            'STRONG_BULLISH': 'BULLISH',
            'WEAK_BULLISH': 'CAUTIOUSLY_BULLISH',
            'NEUTRAL': 'NEUTRAL',
            'WEAK_BEARISH': 'CAUTIOUSLY_BEARISH',
            'STRONG_BEARISH': 'BEARISH',
            'HIGH_VOLATILITY': 'VOLATILE',
            'CRISIS': 'RISK_OFF'
        }
        
        outlook = outlook_map.get(dominant_regime, 'NEUTRAL')
        
        return {
            'outlook': outlook,
            'dominant_regime': dominant_regime,
            'confidence': avg_confidence,
            'index_regimes': index_regimes
        }
    
    def _create_reports(self, index_regimes: Dict, 
                       stock_analysis: Dict, 
                       recommendations: Dict):
        """Create detailed reports"""
        logger.info("Creating reports...")
        
        # 1. Summary report
        self._create_summary_report(index_regimes, stock_analysis, recommendations)
        
        # 2. Detailed position report
        self._create_position_report(stock_analysis, recommendations)
        
        # 3. Risk report
        self._create_risk_report(recommendations)
        
        # 4. JSON report for automated systems
        self._create_json_report(index_regimes, stock_analysis, recommendations)
    
    def _create_summary_report(self, index_regimes: Dict, 
                              stock_analysis: Dict, 
                              recommendations: Dict):
        """Create human-readable summary report"""
        timestamp = datetime.now()
        filename = f"regime_summary_{timestamp.strftime('%Y%m%d')}.txt"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            f.write(f"DAILY MARKET REGIME ANALYSIS\n")
            f.write(f"{'='*60}\n")
            f.write(f"Date: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Market outlook
            outlook = recommendations['market_outlook']
            f.write(f"MARKET OUTLOOK: {outlook['outlook']}\n")
            f.write(f"Confidence: {outlook['confidence']:.2%}\n\n")
            
            # Index regimes
            f.write("INDEX REGIMES:\n")
            f.write("-" * 40 + "\n")
            for index, data in index_regimes.items():
                f.write(f"{index:12} | {data['regime']:15} | {data['confidence']:.2%}\n")
            
            # Position recommendations summary
            f.write(f"\nPOSITION RECOMMENDATIONS:\n")
            f.write("-" * 40 + "\n")
            
            action_counts = {}
            for ticker, rec in recommendations['position_recommendations'].items():
                action = rec.get('action', 'HOLD')
                action_counts[action] = action_counts.get(action, 0) + 1
            
            for action, count in action_counts.items():
                f.write(f"{action}: {count} positions\n")
            
            # Risk alerts
            if recommendations['risk_alerts']:
                f.write(f"\nRISK ALERTS ({len(recommendations['risk_alerts'])}):\n")
                f.write("-" * 40 + "\n")
                for alert in recommendations['risk_alerts']:
                    f.write(f"{alert['ticker']}: {alert['alert']}\n")
                    f.write(f"  Recommended Action: {alert['action']}\n")
            
            # New opportunities
            if recommendations['new_opportunities']:
                f.write(f"\nNEW OPPORTUNITIES ({len(recommendations['new_opportunities'])}):\n")
                f.write("-" * 40 + "\n")
                for opp in recommendations['new_opportunities'][:5]:  # Top 5
                    f.write(f"{opp['ticker']}: {opp['regime']} (conf: {opp['confidence']:.2%})\n")
        
        logger.info(f"Summary report saved to {filepath}")
    
    def _create_position_report(self, stock_analysis: Dict, recommendations: Dict):
        """Create detailed position report"""
        timestamp = datetime.now()
        filename = f"position_details_{timestamp.strftime('%Y%m%d')}.csv"
        filepath = os.path.join(self.output_dir, filename)
        
        # Create DataFrame for positions
        position_data = []
        
        for ticker, rec in recommendations['position_recommendations'].items():
            if ticker in stock_analysis:
                analysis = stock_analysis[ticker]
                
                position_data.append({
                    'ticker': ticker,
                    'regime': analysis['regime'],
                    'confidence': analysis['confidence'],
                    'action': rec.get('action', 'HOLD'),
                    'position_size_factor': rec.get('position_size_factor', 1.0),
                    'sl_multiplier_long': rec['stop_loss_multipliers']['long'],
                    'sl_multiplier_short': rec['stop_loss_multipliers']['short'],
                    'volatility': analysis['metrics'].get('volatility', 0),
                    'trend_strength': analysis['metrics'].get('trend_strength', 0),
                    'urgency': rec.get('urgency', 'NORMAL')
                })
        
        df = pd.DataFrame(position_data)
        df.to_csv(filepath, index=False)
        
        logger.info(f"Position report saved to {filepath}")
    
    def _create_risk_report(self, recommendations: Dict):
        """Create risk management report"""
        timestamp = datetime.now()
        filename = f"risk_report_{timestamp.strftime('%Y%m%d')}.txt"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            f.write(f"RISK MANAGEMENT REPORT\n")
            f.write(f"{'='*60}\n")
            f.write(f"Date: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Market risk level
            outlook = recommendations['market_outlook']['outlook']
            risk_levels = {
                'BULLISH': 'LOW',
                'CAUTIOUSLY_BULLISH': 'LOW-MODERATE',
                'NEUTRAL': 'MODERATE',
                'CAUTIOUSLY_BEARISH': 'MODERATE-HIGH',
                'BEARISH': 'HIGH',
                'VOLATILE': 'HIGH',
                'RISK_OFF': 'EXTREME'
            }
            
            risk_level = risk_levels.get(outlook, 'MODERATE')
            f.write(f"OVERALL MARKET RISK: {risk_level}\n\n")
            
            # Position sizing recommendations
            f.write("POSITION SIZING RECOMMENDATIONS:\n")
            f.write("-" * 40 + "\n")
            
            if risk_level in ['HIGH', 'EXTREME']:
                f.write("- Reduce overall portfolio exposure\n")
                f.write("- Maximum position size: 2% per position\n")
                f.write("- Consider hedging strategies\n")
            elif risk_level in ['MODERATE-HIGH']:
                f.write("- Maintain defensive positioning\n")
                f.write("- Maximum position size: 3% per position\n")
                f.write("- Focus on high-quality setups only\n")
            else:
                f.write("- Normal position sizing can be maintained\n")
                f.write("- Maximum position size: 5% per position\n")
                f.write("- Look for opportunities in strong sectors\n")
            
            # Stop loss recommendations
            f.write("\nSTOP LOSS ADJUSTMENTS:\n")
            f.write("-" * 40 + "\n")
            
            # Group by regime type
            regime_groups = {}
            for ticker, rec in recommendations['position_recommendations'].items():
                sl_mult = rec['stop_loss_multipliers']
                key = f"{sl_mult['long']:.1f}x/{sl_mult['short']:.1f}x"
                
                if key not in regime_groups:
                    regime_groups[key] = []
                regime_groups[key].append(ticker)
            
            for key, tickers in regime_groups.items():
                long_mult, short_mult = key.split('/')
                f.write(f"\nLong: {long_mult}, Short: {short_mult}\n")
                f.write(f"Tickers: {', '.join(tickers[:10])}")
                if len(tickers) > 10:
                    f.write(f" and {len(tickers)-10} more")
                f.write("\n")
        
        logger.info(f"Risk report saved to {filepath}")
    
    def _create_json_report(self, index_regimes: Dict, 
                           stock_analysis: Dict, 
                           recommendations: Dict):
        """Create JSON report for automated systems"""
        timestamp = datetime.now()
        filename = f"regime_analysis_{timestamp.strftime('%Y%m%d')}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        report = {
            'timestamp': timestamp.isoformat(),
            'index_regimes': index_regimes,
            'stock_analysis': stock_analysis,
            'recommendations': recommendations,
            'metadata': {
                'version': '1.0',
                'analyzer': 'MarketRegimeML'
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"JSON report saved to {filepath}")
    
    def _update_state(self, stock_analysis: Dict, recommendations: Dict):
        """Update state with regime information"""
        try:
            state = self.state_manager.load_state()
            
            # Add regime information to state
            if 'regime_analysis' not in state:
                state['regime_analysis'] = {}
            
            state['regime_analysis']['last_updated'] = datetime.now().isoformat()
            state['regime_analysis']['market_outlook'] = recommendations['market_outlook']
            state['regime_analysis']['stock_regimes'] = {}
            
            for ticker, analysis in stock_analysis.items():
                state['regime_analysis']['stock_regimes'][ticker] = {
                    'regime': analysis['regime'],
                    'confidence': analysis['confidence'],
                    'position_adjustment': analysis['position_adjustment'],
                    'stop_loss_multipliers': analysis['stop_loss_multipliers']
                }
            
            self.state_manager.save_state(state)
            logger.info("State updated with regime analysis")
            
        except Exception as e:
            logger.error(f"Error updating state: {str(e)}")
    
    def _load_data(self, ticker: str):
        """Load historical data for analysis"""
        try:
            # Try loading from BT data directory
            file_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'BT', 'data', f'{ticker}_day.csv'
            )
            
            if os.path.exists(file_path):
                data = pd.read_csv(file_path)
                data['date'] = pd.to_datetime(data['date'])
                data = data.set_index('date')
                return data
            
            # Try fetching from API if file doesn't exist
            # This would use the DataHandler in production
            return None
            
        except Exception as e:
            logger.error(f"Error loading data for {ticker}: {str(e)}")
            return None
    
    def _get_reference_index(self, ticker: str) -> str:
        """Determine reference index for a stock"""
        # This is a simplified version
        # In production, this would use market cap data
        small_caps = ['ACI', 'CCL', 'RRKABEL', 'ELECON']
        mid_caps = ['COFORGE', 'CREDITACC', 'SCHAEFFLER', 'TIMKEN']
        
        if ticker in small_caps:
            return 'SMALLCAP'
        elif ticker in mid_caps:
            return 'MIDCAP'
        else:
            return 'TOP100CASE'
    
    def _get_watchlist(self):
        """Get watchlist of stocks to analyze"""
        # This could be loaded from a configuration file
        return []

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Daily Market Regime Analysis')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    
    args = parser.parse_args()
    
    # Initialize analyzer
    analyzer = DailyRegimeAnalyzer(args.config)
    
    # Run analysis
    results = analyzer.run_daily_analysis()
    
    if results['status'] == 'success':
        logger.info("Daily regime analysis completed successfully")
        print("\nAnalysis complete. Check the results directory for reports.")
    else:
        logger.error(f"Analysis failed: {results.get('error', 'Unknown error')}")
        sys.exit(1)

if __name__ == "__main__":
    main()