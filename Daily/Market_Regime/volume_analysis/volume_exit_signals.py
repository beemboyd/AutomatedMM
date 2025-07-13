
def calculate_exhaustion_score(ticker_data):
    """Calculate exhaustion score for a ticker based on volume-price anomalies"""
    score = 0
    
    # Price Rejection: High volume but low momentum
    if ticker_data['volume_ratio'] > ticker_data['volume_ratio_75th_percentile'] and        ticker_data['momentum_5d'] < ticker_data['momentum_25th_percentile']:
        score += 2
    
    # Volume Exhaustion: Very high volume with weak price action
    if ticker_data['volume_ratio'] > 3 and ticker_data['momentum_5d'] < 5:
        score += 3
    
    # Narrow Range High Volume
    price_spread_pct = (ticker_data['atr'] / ticker_data['close']) * 100
    if ticker_data['volume_ratio'] > 2 and price_spread_pct < 2:
        score += 1
    
    return score

def should_exit_position(ticker, current_data, position_data):
    """Determine if position should be exited based on volume anomalies"""
    
    # Calculate metrics
    volume_efficiency = current_data['momentum_5d'] / current_data['volume_ratio']
    exhaustion_score = calculate_exhaustion_score(current_data)
    
    # Exit conditions
    exit_reasons = []
    
    # Rule 1: Volume Exhaustion
    if current_data['volume_ratio'] > 3 and current_data['momentum_5d'] < 5:
        exit_reasons.append("Volume exhaustion detected")
    
    # Rule 2: Low efficiency
    if volume_efficiency < 0.5:
        exit_reasons.append("Volume efficiency breakdown")
    
    # Rule 3: High exhaustion score
    if exhaustion_score >= 4:
        exit_reasons.append(f"High exhaustion score: {exhaustion_score}")
    
    # Rule 4: Narrow range rejection (intraday check)
    if current_data['volume_ratio'] > 2:
        daily_range_pct = ((current_data['high'] - current_data['low']) / current_data['close']) * 100
        close_position_pct = (current_data['close'] - current_data['low']) / (current_data['high'] - current_data['low'])
        
        if daily_range_pct < 1.5 and close_position_pct < 0.3:  # Close in bottom 30% of range
            exit_reasons.append("Narrow range rejection pattern")
    
    return len(exit_reasons) > 0, exit_reasons

def adjust_stop_loss_by_exhaustion(ticker, current_stop_loss, atr, exhaustion_score):
    """Adjust stop loss based on exhaustion score"""
    
    if exhaustion_score == 0:
        # No adjustment needed
        return current_stop_loss
    elif exhaustion_score <= 2:
        # Minor tightening
        return current_stop_loss + (0.25 * atr)
    elif exhaustion_score == 3:
        # Moderate tightening
        return current_stop_loss + (0.5 * atr)
    else:  # exhaustion_score >= 4
        # Aggressive tightening
        return current_stop_loss + (0.75 * atr)
