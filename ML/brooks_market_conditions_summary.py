#!/usr/bin/env python3
"""
Brooks Strategy Market Conditions Summary

Simple script to identify the market conditions that led to Brooks strategy success.
This can be used to identify similar future conditions.

Key Findings from Analysis Period (May 20-23, 2025):
"""

def get_brooks_success_conditions():
    """Return the market conditions that led to Brooks strategy success"""
    return {
        'market_signature': {
            'market_type': 'Sideways_Choppy',
            'volatility_regime': 'Normal_Volatility', 
            'breadth_regime': 'Selective_Participation',
            'volume_regime': 'Normal_Volume_Activity',
            'risk_level': 'Moderate_Risk',
            'opportunity_score': 48
        },
        
        'key_metrics': {
            'avg_daily_return': 0.40,  # %
            'positive_days_pct': 50.0,  # %
            'avg_daily_range': 3.17,  # %
            'positive_participation': 44.0,  # %
            'volume_expansion_days': 21.4,  # %
            'gap_activity': 98.9,  # %
            'extreme_moves': 1.7  # %
        },
        
        'optimal_conditions_for_brooks': {
            'market_direction': 'Sideways to mildly positive (0-1% daily avg)',
            'volatility': 'Normal range (2-4% daily)',
            'participation': 'Selective (40-50% positive)',
            'gaps': 'High gap activity (>90%)',
            'risk': 'Moderate risk environment',
            'volume': 'Normal activity levels'
        },
        
        'strategy_deployment_criteria': {
            'deploy_when': [
                'Market showing choppy/sideways behavior',
                'Daily volatility in 2-4% range',
                'Market participation 40-50%',
                'High gap opening activity',
                'No extreme trending conditions',
                'Moderate risk environment'
            ],
            
            'avoid_when': [
                'Strong trending markets (>1% daily avg)',
                'Very low volatility (<2% daily range)',
                'Very high volatility (>5% daily range)',
                'Extreme market participation (<30% or >70%)',
                'High stress/extreme move environment'
            ]
        }
    }

def print_deployment_guide():
    """Print a practical guide for when to deploy Brooks strategies"""
    conditions = get_brooks_success_conditions()
    
    print("\n" + "="*70)
    print("BROOKS STRATEGY DEPLOYMENT GUIDE")
    print("="*70)
    print("Based on successful period: May 20-23, 2025")
    print()
    
    print("🟢 DEPLOY BROOKS STRATEGIES WHEN:")
    for condition in conditions['strategy_deployment_criteria']['deploy_when']:
        print(f"  • {condition}")
    print()
    
    print("🔴 AVOID BROOKS STRATEGIES WHEN:")
    for condition in conditions['strategy_deployment_criteria']['avoid_when']:
        print(f"  • {condition}")
    print()
    
    print("📊 OPTIMAL METRICS RANGES:")
    optimal = conditions['optimal_conditions_for_brooks']
    for key, value in optimal.items():
        print(f"  • {key.replace('_', ' ').title()}: {value}")
    print()
    
    print("💡 MONITORING CHECKLIST:")
    print("  • Daily market return: Target 0-1% range")
    print("  • Daily volatility: Target 2-4% range") 
    print("  • Positive participation: Target 40-50%")
    print("  • Gap activity: Look for >90%")
    print("  • Avoid days with >5% extreme moves")
    print("="*70)

if __name__ == "__main__":
    print_deployment_guide()
    
    # Get conditions for programmatic use
    conditions = get_brooks_success_conditions()
    print(f"\nOpportunity Score during success period: {conditions['market_signature']['opportunity_score']}/100")