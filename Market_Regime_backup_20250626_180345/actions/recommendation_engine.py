"""
Recommendation Engine Module

Translates regime insights into specific trading actions and recommendations.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
import json
import os


class RecommendationEngine:
    """Generate actionable trading recommendations based on market regime"""
    
    def __init__(self, config_path: str = None):
        """Initialize recommendation engine"""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                     'config', 'regime_config.json')
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.action_params = self.config['action_parameters']
        self.sector_prefs = self.config['sector_preferences']
        self.logger = logging.getLogger(__name__)
        
    def generate_recommendations(self, regime_analysis: Dict[str, any],
                               portfolio_state: Optional[Dict] = None) -> Dict[str, any]:
        """
        Generate comprehensive trading recommendations
        
        Args:
            regime_analysis: Output from RegimeDetector
            portfolio_state: Current portfolio state (positions, capital, etc.)
            
        Returns:
            Dictionary of recommendations
        """
        try:
            regime = regime_analysis['regime']
            confidence = regime_analysis['confidence']
            indicators = regime_analysis.get('indicators', {})
            
            recommendations = {
                'timestamp': datetime.now().isoformat(),
                'regime': regime,
                'confidence': confidence,
                'position_sizing': self._get_position_sizing_recommendations(regime, confidence),
                'risk_management': self._get_risk_management_recommendations(regime, indicators),
                'capital_deployment': self._get_capital_deployment_recommendations(regime, confidence),
                'sector_preferences': self._get_sector_recommendations(regime),
                'specific_actions': self._get_specific_actions(regime, confidence, portfolio_state),
                'alerts': self._generate_alerts(regime_analysis)
            }
            
            # Add portfolio-specific recommendations if state provided
            if portfolio_state:
                portfolio_recs = self._get_portfolio_specific_recommendations(
                    regime, portfolio_state, indicators
                )
                recommendations['portfolio_actions'] = portfolio_recs
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Error generating recommendations: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _get_position_sizing_recommendations(self, regime: str, confidence: float) -> Dict[str, any]:
        """Get position sizing recommendations"""
        base_multiplier = self.action_params['position_sizing'].get(regime, 0.5)
        
        # Adjust based on confidence
        confidence_adjustment = 0.8 + (0.4 * confidence)  # 0.8 to 1.2 range
        final_multiplier = base_multiplier * confidence_adjustment
        
        # Calculate specific position sizes
        recommendations = {
            'size_multiplier': round(final_multiplier, 2),
            'max_position_size': self._calculate_max_position_size(regime, final_multiplier),
            'recommended_positions': self._get_recommended_position_count(regime),
            'concentration_limit': self._get_concentration_limit(regime)
        }
        
        # Add specific guidance
        if regime in ['strong_bear', 'crisis']:
            recommendations['guidance'] = "Minimize new positions, consider cash preservation"
        elif regime == 'volatile':
            recommendations['guidance'] = "Reduce position sizes, increase diversification"
        elif regime in ['strong_bull', 'bull']:
            recommendations['guidance'] = "Normal to increased position sizes acceptable"
        else:
            recommendations['guidance'] = "Moderate position sizes, selective entry"
            
        return recommendations
    
    def _get_risk_management_recommendations(self, regime: str, indicators: Dict) -> Dict[str, any]:
        """Get risk management recommendations"""
        stop_loss_multiplier = self.action_params['stop_loss_multiplier'].get(regime, 1.0)
        
        recommendations = {
            'stop_loss_multiplier': stop_loss_multiplier,
            'stop_loss_type': self._get_stop_loss_type(regime),
            'trailing_stop': self._should_use_trailing_stop(regime),
            'risk_per_trade': self._get_risk_per_trade(regime),
            'portfolio_heat': self._get_max_portfolio_heat(regime)
        }
        
        # Volatility-based adjustments
        vol_regime = indicators.get('volatility_regime', 'normal')
        if vol_regime in ['high', 'extreme']:
            recommendations['volatility_adjustment'] = {
                'stop_loss_multiplier': stop_loss_multiplier * 0.8,
                'wider_stops': False,
                'reason': "High volatility - tighter stops recommended"
            }
        
        # Add specific risk actions
        risk_actions = []
        
        if regime in ['bear', 'strong_bear', 'crisis']:
            risk_actions.append("Review and tighten all stop losses")
            risk_actions.append("Consider hedging strategies")
            risk_actions.append("Reduce leverage if any")
            
        if regime == 'volatile':
            risk_actions.append("Use volatility-based position sizing")
            risk_actions.append("Avoid gap risk - use limit orders")
            risk_actions.append("Monitor positions more frequently")
            
        recommendations['specific_actions'] = risk_actions
        
        return recommendations
    
    def _get_capital_deployment_recommendations(self, regime: str, confidence: float) -> Dict[str, any]:
        """Get capital deployment recommendations"""
        deployment_rate = self.action_params['new_capital_deployment'].get(regime, 0.5)
        
        # Adjust for confidence
        adjusted_rate = deployment_rate * confidence
        
        recommendations = {
            'deployment_rate': round(adjusted_rate, 2),
            'cash_allocation': self._get_cash_allocation(regime),
            'entry_strategy': self._get_entry_strategy(regime),
            'timing_guidance': self._get_timing_guidance(regime)
        }
        
        # Capital preservation in adverse regimes
        if regime in ['strong_bear', 'crisis']:
            recommendations['preservation_mode'] = True
            recommendations['guidance'] = "Focus on capital preservation, avoid new deployments"
        elif regime == 'bear':
            recommendations['selective_mode'] = True
            recommendations['guidance'] = "Highly selective deployment, quality focus"
        else:
            recommendations['guidance'] = self._get_deployment_guidance(regime)
            
        return recommendations
    
    def _get_sector_recommendations(self, regime: str) -> Dict[str, any]:
        """Get sector-specific recommendations"""
        preferred_sectors = self.sector_prefs.get(regime, [])
        
        recommendations = {
            'preferred_sectors': preferred_sectors,
            'sector_allocation': self._get_sector_allocation(regime, preferred_sectors),
            'avoid_sectors': self._get_sectors_to_avoid(regime),
            'rotation_signals': self._check_sector_rotation(regime)
        }
        
        # Add rationale
        if regime in ['strong_bull', 'bull']:
            recommendations['rationale'] = "Focus on growth and cyclical sectors"
        elif regime in ['bear', 'strong_bear']:
            recommendations['rationale'] = "Defensive sectors and quality focus"
        elif regime == 'volatile':
            recommendations['rationale'] = "Low beta and defensive positioning"
        else:
            recommendations['rationale'] = "Balanced sector allocation"
            
        return recommendations
    
    def _get_specific_actions(self, regime: str, confidence: float, 
                             portfolio_state: Optional[Dict]) -> List[Dict]:
        """Generate specific actionable recommendations"""
        actions = []
        
        # Regime-based actions
        if regime == 'crisis':
            actions.extend([
                {
                    'priority': 'HIGH',
                    'action': 'EXIT_POSITIONS',
                    'description': 'Close all speculative positions immediately',
                    'reason': 'Crisis regime detected'
                },
                {
                    'priority': 'HIGH',
                    'action': 'RAISE_CASH',
                    'description': 'Increase cash allocation to 70-80%',
                    'reason': 'Capital preservation in crisis'
                }
            ])
            
        elif regime == 'strong_bear':
            actions.extend([
                {
                    'priority': 'HIGH',
                    'action': 'REDUCE_EXPOSURE',
                    'description': 'Reduce portfolio exposure by 50%',
                    'reason': 'Strong bear market conditions'
                },
                {
                    'priority': 'MEDIUM',
                    'action': 'TIGHTEN_STOPS',
                    'description': 'Tighten all stop losses to 0.7x normal',
                    'reason': 'Increased downside risk'
                }
            ])
            
        elif regime == 'volatile':
            actions.extend([
                {
                    'priority': 'HIGH',
                    'action': 'REDUCE_POSITION_SIZES',
                    'description': 'Cut position sizes by 40%',
                    'reason': 'High volatility regime'
                },
                {
                    'priority': 'MEDIUM',
                    'action': 'INCREASE_DIVERSIFICATION',
                    'description': 'Ensure no position > 5% of portfolio',
                    'reason': 'Volatility risk management'
                }
            ])
            
        elif regime in ['bull', 'strong_bull']:
            actions.extend([
                {
                    'priority': 'MEDIUM',
                    'action': 'DEPLOY_CAPITAL',
                    'description': 'Deploy idle capital into trending positions',
                    'reason': f'{regime.replace("_", " ").title()} market conditions'
                },
                {
                    'priority': 'LOW',
                    'action': 'PYRAMID_WINNERS',
                    'description': 'Add to winning positions on pullbacks',
                    'reason': 'Trending market opportunity'
                }
            ])
        
        # Confidence-based actions
        if confidence < 0.5:
            actions.append({
                'priority': 'HIGH',
                'action': 'REDUCE_ACTIVITY',
                'description': 'Reduce trading activity due to low regime confidence',
                'reason': f'Regime confidence only {confidence:.1%}'
            })
        
        # Portfolio-specific actions
        if portfolio_state:
            portfolio_actions = self._generate_portfolio_actions(regime, portfolio_state)
            actions.extend(portfolio_actions)
        
        # Sort by priority
        priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        actions.sort(key=lambda x: priority_order.get(x['priority'], 3))
        
        return actions
    
    def _generate_alerts(self, regime_analysis: Dict) -> List[Dict]:
        """Generate alerts based on regime analysis"""
        alerts = []
        
        # Regime change alert
        if regime_analysis.get('regime_changed', False):
            alerts.append({
                'type': 'REGIME_CHANGE',
                'severity': 'HIGH',
                'message': f"Market regime changed to {regime_analysis['regime']}",
                'action_required': True
            })
        
        # Low confidence alert
        if regime_analysis['confidence'] < 0.4:
            alerts.append({
                'type': 'LOW_CONFIDENCE',
                'severity': 'MEDIUM',
                'message': f"Low regime confidence: {regime_analysis['confidence']:.1%}",
                'action_required': False
            })
        
        # Crisis/Extreme conditions
        if regime_analysis['regime'] in ['crisis', 'strong_bear']:
            alerts.append({
                'type': 'EXTREME_CONDITIONS',
                'severity': 'CRITICAL',
                'message': f"{regime_analysis['regime'].upper()} conditions detected",
                'action_required': True
            })
        
        # Volatility spike
        indicators = regime_analysis.get('indicators', {})
        if indicators.get('volatility_regime') in ['extreme', 'very_high']:
            alerts.append({
                'type': 'VOLATILITY_SPIKE',
                'severity': 'HIGH',
                'message': f"Extreme volatility detected: {indicators.get('volatility_regime')}",
                'action_required': True
            })
        
        return alerts
    
    def _get_portfolio_specific_recommendations(self, regime: str, 
                                              portfolio_state: Dict,
                                              indicators: Dict) -> Dict[str, any]:
        """Generate portfolio-specific recommendations"""
        recommendations = {}
        
        # Check current exposure vs recommended
        current_exposure = portfolio_state.get('total_exposure', 0)
        max_exposure = self.action_params['max_portfolio_exposure'].get(regime, 0.7)
        
        if current_exposure > max_exposure:
            recommendations['reduce_exposure'] = {
                'current': current_exposure,
                'target': max_exposure,
                'reduction_needed': current_exposure - max_exposure,
                'priority': 'HIGH'
            }
        
        # Position-specific recommendations
        if 'positions' in portfolio_state:
            position_recs = self._analyze_positions(portfolio_state['positions'], regime, indicators)
            recommendations['position_actions'] = position_recs
        
        # Cash management
        cash_percentage = portfolio_state.get('cash_percentage', 0)
        target_cash = self._get_cash_allocation(regime)
        
        if abs(cash_percentage - target_cash) > 0.1:
            recommendations['cash_adjustment'] = {
                'current': cash_percentage,
                'target': target_cash,
                'action': 'increase' if target_cash > cash_percentage else 'decrease'
            }
        
        return recommendations
    
    # Helper methods
    def _calculate_max_position_size(self, regime: str, multiplier: float) -> float:
        """Calculate maximum position size as percentage of portfolio"""
        base_sizes = {
            'strong_bull': 0.15,
            'bull': 0.12,
            'neutral': 0.10,
            'bear': 0.08,
            'strong_bear': 0.05,
            'volatile': 0.07,
            'crisis': 0.03
        }
        
        base_size = base_sizes.get(regime, 0.10)
        return round(base_size * multiplier, 3)
    
    def _get_recommended_position_count(self, regime: str) -> Dict[str, int]:
        """Get recommended number of positions"""
        position_counts = {
            'strong_bull': {'min': 8, 'max': 15},
            'bull': {'min': 6, 'max': 12},
            'neutral': {'min': 5, 'max': 10},
            'bear': {'min': 3, 'max': 8},
            'strong_bear': {'min': 2, 'max': 5},
            'volatile': {'min': 4, 'max': 10},
            'crisis': {'min': 0, 'max': 3}
        }
        
        return position_counts.get(regime, {'min': 5, 'max': 10})
    
    def _get_concentration_limit(self, regime: str) -> float:
        """Get maximum concentration per position"""
        limits = {
            'strong_bull': 0.20,
            'bull': 0.15,
            'neutral': 0.12,
            'bear': 0.10,
            'strong_bear': 0.08,
            'volatile': 0.10,
            'crisis': 0.05
        }
        
        return limits.get(regime, 0.12)
    
    def _get_stop_loss_type(self, regime: str) -> str:
        """Determine stop loss type based on regime"""
        if regime in ['strong_bull', 'bull']:
            return 'trailing'
        elif regime in ['volatile']:
            return 'volatility_based'
        else:
            return 'fixed'
    
    def _should_use_trailing_stop(self, regime: str) -> bool:
        """Determine if trailing stops should be used"""
        return regime in ['strong_bull', 'bull', 'neutral']
    
    def _get_risk_per_trade(self, regime: str) -> float:
        """Get recommended risk per trade as percentage"""
        risk_levels = {
            'strong_bull': 0.02,
            'bull': 0.015,
            'neutral': 0.01,
            'bear': 0.008,
            'strong_bear': 0.005,
            'volatile': 0.008,
            'crisis': 0.003
        }
        
        return risk_levels.get(regime, 0.01)
    
    def _get_max_portfolio_heat(self, regime: str) -> float:
        """Get maximum portfolio heat (total risk)"""
        heat_levels = {
            'strong_bull': 0.08,
            'bull': 0.06,
            'neutral': 0.05,
            'bear': 0.04,
            'strong_bear': 0.02,
            'volatile': 0.04,
            'crisis': 0.01
        }
        
        return heat_levels.get(regime, 0.05)
    
    def _get_cash_allocation(self, regime: str) -> float:
        """Get recommended cash allocation"""
        cash_levels = {
            'strong_bull': 0.05,
            'bull': 0.10,
            'neutral': 0.20,
            'bear': 0.40,
            'strong_bear': 0.60,
            'volatile': 0.30,
            'crisis': 0.80
        }
        
        return cash_levels.get(regime, 0.20)
    
    def _get_entry_strategy(self, regime: str) -> str:
        """Get recommended entry strategy"""
        strategies = {
            'strong_bull': 'aggressive_breakouts',
            'bull': 'pullback_entries',
            'neutral': 'range_trading',
            'bear': 'oversold_bounces',
            'strong_bear': 'avoid_longs',
            'volatile': 'scale_in',
            'crisis': 'no_entries'
        }
        
        return strategies.get(regime, 'selective')
    
    def _get_timing_guidance(self, regime: str) -> str:
        """Get timing guidance for entries"""
        if regime in ['strong_bull']:
            return "Enter on any weakness, strength begets strength"
        elif regime == 'bull':
            return "Wait for pullbacks to support or moving averages"
        elif regime == 'neutral':
            return "Buy support, sell resistance in range"
        elif regime == 'bear':
            return "Only enter on extreme oversold conditions"
        elif regime in ['strong_bear', 'crisis']:
            return "Avoid new long entries entirely"
        elif regime == 'volatile':
            return "Use wide scales, avoid chasing moves"
        else:
            return "Selective entry on high-probability setups"
    
    def _get_deployment_guidance(self, regime: str) -> str:
        """Get capital deployment guidance"""
        if regime == 'strong_bull':
            return "Deploy aggressively on pullbacks, maintain high exposure"
        elif regime == 'bull':
            return "Steady deployment, increase on weakness"
        elif regime == 'neutral':
            return "Selective deployment on extreme levels"
        elif regime == 'volatile':
            return "Small positions, wide scales, patience"
        else:
            return "Preserve capital, wait for better conditions"
    
    def _get_sector_allocation(self, regime: str, preferred_sectors: List[str]) -> Dict[str, float]:
        """Get sector allocation recommendations"""
        allocations = {}
        
        if not preferred_sectors:
            return allocations
        
        # Base allocation per sector
        base_allocation = 1.0 / len(preferred_sectors)
        
        # Adjust based on regime
        if regime in ['strong_bull', 'bull']:
            # Overweight growth sectors
            for i, sector in enumerate(preferred_sectors):
                if i < len(preferred_sectors) // 2:
                    allocations[sector] = base_allocation * 1.2
                else:
                    allocations[sector] = base_allocation * 0.8
        else:
            # Equal weight or defensive tilt
            for sector in preferred_sectors:
                allocations[sector] = base_allocation
        
        return allocations
    
    def _get_sectors_to_avoid(self, regime: str) -> List[str]:
        """Get sectors to avoid based on regime"""
        avoid_sectors = {
            'strong_bull': [],
            'bull': ['Utilities'],
            'neutral': ['High Beta'],
            'bear': ['Realty', 'Auto', 'Capital Goods'],
            'strong_bear': ['Cyclicals', 'Financials', 'Realty'],
            'volatile': ['High Beta', 'Small Caps'],
            'crisis': ['All except FMCG, Pharma']
        }
        
        return avoid_sectors.get(regime, [])
    
    def _check_sector_rotation(self, regime: str) -> Dict[str, str]:
        """Check for sector rotation signals"""
        rotation_signals = {
            'strong_bull': 'Rotate into growth and momentum sectors',
            'bull': 'Maintain growth tilt with some value',
            'neutral': 'Balanced allocation across sectors',
            'bear': 'Rotate into defensive sectors',
            'strong_bear': 'Maximum defensive positioning',
            'volatile': 'Reduce sector concentration',
            'crisis': 'Cash and defensive only'
        }
        
        return {
            'signal': rotation_signals.get(regime, 'No clear rotation signal'),
            'strength': 'strong' if regime in ['strong_bull', 'strong_bear', 'crisis'] else 'moderate'
        }
    
    def _generate_portfolio_actions(self, regime: str, portfolio_state: Dict) -> List[Dict]:
        """Generate portfolio-specific actions"""
        actions = []
        
        # Check for overexposure
        if portfolio_state.get('total_exposure', 0) > 0.9 and regime in ['bear', 'strong_bear', 'volatile']:
            actions.append({
                'priority': 'HIGH',
                'action': 'REDUCE_EXPOSURE',
                'description': f'Reduce total exposure from {portfolio_state["total_exposure"]:.1%} to <70%',
                'reason': 'Overexposed in adverse regime'
            })
        
        # Check for concentrated positions
        if 'positions' in portfolio_state:
            for position in portfolio_state['positions']:
                if position.get('allocation', 0) > 0.15 and regime in ['volatile', 'bear']:
                    actions.append({
                        'priority': 'MEDIUM',
                        'action': 'REDUCE_CONCENTRATION',
                        'description': f'Reduce {position["symbol"]} from {position["allocation"]:.1%} to <10%',
                        'reason': 'Position too concentrated for current regime'
                    })
        
        return actions
    
    def _analyze_positions(self, positions: List[Dict], regime: str, indicators: Dict) -> List[Dict]:
        """Analyze individual positions and generate recommendations"""
        position_actions = []
        
        for position in positions:
            # Check position performance vs regime
            if position.get('unrealized_pnl_percent', 0) < -10 and regime in ['bear', 'strong_bear']:
                position_actions.append({
                    'symbol': position['symbol'],
                    'action': 'EXIT',
                    'reason': 'Large loss in bear regime',
                    'priority': 'HIGH'
                })
            
            # Check position volatility
            if position.get('volatility', 0) > 30 and regime == 'volatile':
                position_actions.append({
                    'symbol': position['symbol'],
                    'action': 'REDUCE',
                    'reason': 'High volatility position in volatile regime',
                    'priority': 'MEDIUM'
                })
        
        return position_actions