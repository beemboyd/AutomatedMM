#!/usr/bin/env python3
"""
Tom DeMark Indicator Calculations - Full Implementation

Implements:
- TD Moving Average I (TD MA I)
- TD Moving Average II (TD MA II)
- TD Sequential Setup (9-count)
- TD Countdown (13-count)
- TDST Support/Resistance
- Setup Validity (lowest low of bars 1-9)
- Higher Low Tracking
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field


@dataclass
class TDState:
    """Current state of TD indicators"""
    # TD MA I
    td_ma1_active: bool = False
    td_ma1_value: float = 0.0
    td_ma1_bars_remaining: int = 0

    # TD MA II
    td_ma2_active: bool = False
    td_ma2_value: float = 0.0
    td_ma2_bars_remaining: int = 0

    # TD Setup
    td_setup_count: int = 0
    td_setup_complete: bool = False
    td_setup_bar9_close: float = 0.0  # Close of Setup bar 9
    td_setup_bar9_range_pct: float = 0.0  # Where bar 9 closed in its range (0-1)
    td_setup_lowest_low: float = 0.0  # Lowest low of bars 1-9 (Setup validity)
    bars_since_setup9: int = 0  # Bars since Setup 9 completed
    highest_close_since_setup9: float = 0.0  # For follow-through check

    # TDST
    tdst_support: float = 0.0
    tdst_active: bool = False

    # TD Countdown
    td_countdown: int = 0
    td_countdown_complete: bool = False

    # Higher Lows (for swing structure)
    recent_higher_low: float = 0.0


class TDIndicatorCalculator:
    """
    Tom DeMark Indicator Calculator - Full Implementation

    Calculates TD MA I, TD MA II, TD Setup, TD Countdown, and TDST levels
    using daily OHLC data.
    """

    def __init__(self, lookback_period: int = 12, ma_period: int = 5, extension_bars: int = 4):
        """
        Initialize TD calculator

        Args:
            lookback_period: Bars to look back for TD MA conditions (default 12)
            ma_period: Period for TD MA calculations (default 5)
            extension_bars: Bars to extend TD MA (default 4)
        """
        self.lookback_period = lookback_period
        self.ma_period = ma_period
        self.extension_bars = extension_bars

    def calculate_td_ma1_bullish(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Bullish TD MA I

        Condition: Bar's low is higher than the lows of prior 12 bars
        Value: 5-bar SMA of lows
        Duration: 4 bars, extends if re-triggered
        """
        df = df.copy()

        # Calculate rolling minimum of lows for prior 12 bars
        df['lowest_low_12'] = df['low'].shift(1).rolling(window=self.lookback_period).min()

        # Trigger: current low > lowest low of prior 12 bars
        df['td_ma1_trigger'] = df['low'] > df['lowest_low_12']

        # Calculate 5-bar SMA of lows
        df['td_ma1_sma'] = df['low'].rolling(window=self.ma_period).mean()

        # Track active state with extension logic
        td_ma1_active = []
        td_ma1_value = []
        bars_remaining = 0
        current_value = 0.0

        for i in range(len(df)):
            if i >= self.lookback_period and df['td_ma1_trigger'].iloc[i]:
                # New trigger or continuation
                bars_remaining = self.extension_bars
                current_value = df['td_ma1_sma'].iloc[i] if not pd.isna(df['td_ma1_sma'].iloc[i]) else 0.0

            if bars_remaining > 0:
                td_ma1_active.append(True)
                td_ma1_value.append(current_value)
                bars_remaining -= 1
            else:
                td_ma1_active.append(False)
                td_ma1_value.append(0.0)

        df['td_ma1_active'] = td_ma1_active
        df['td_ma1_value'] = td_ma1_value

        return df

    def calculate_td_ma2_bullish(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Bullish TD MA II

        Condition: Bar's close is higher than the closes of prior 12 bars
        Value: 5-bar SMA of closes
        Duration: 4 bars, extends if re-triggered
        """
        df = df.copy()

        # Calculate rolling maximum of closes for prior 12 bars
        df['highest_close_12'] = df['close'].shift(1).rolling(window=self.lookback_period).max()

        # Trigger: current close > highest close of prior 12 bars
        df['td_ma2_trigger'] = df['close'] > df['highest_close_12']

        # Calculate 5-bar SMA of closes
        df['td_ma2_sma'] = df['close'].rolling(window=self.ma_period).mean()

        # Track active state with extension logic
        td_ma2_active = []
        td_ma2_value = []
        bars_remaining = 0
        current_value = 0.0

        for i in range(len(df)):
            if i >= self.lookback_period and df['td_ma2_trigger'].iloc[i]:
                bars_remaining = self.extension_bars
                current_value = df['td_ma2_sma'].iloc[i] if not pd.isna(df['td_ma2_sma'].iloc[i]) else 0.0

            if bars_remaining > 0:
                td_ma2_active.append(True)
                td_ma2_value.append(current_value)
                bars_remaining -= 1
            else:
                td_ma2_active.append(False)
                td_ma2_value.append(0.0)

        df['td_ma2_active'] = td_ma2_active
        df['td_ma2_value'] = td_ma2_value

        return df

    def calculate_td_setup_bullish(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Bullish TD Sequential Setup (9-count)

        Condition: Close[n] > Close[n-4] for 9 consecutive bars
        Also tracks:
        - Setup bar 9 info (close, range position)
        - Lowest low of bars 1-9 (Setup validity level)
        - Bars since Setup 9 completed
        - Highest close since Setup 9 (for follow-through check)
        """
        df = df.copy()

        # Condition: close > close 4 bars earlier
        df['setup_condition'] = df['close'] > df['close'].shift(4)

        # Initialize tracking columns
        setup_count = []
        setup_complete = []
        setup_bar9_close = []
        setup_bar9_range_pct = []
        setup_lowest_low = []
        bars_since_setup9 = []
        highest_close_since_setup9 = []

        count = 0
        current_setup_lowest = 0.0
        current_bar9_close = 0.0
        current_bar9_range_pct = 0.0
        bars_since = 0
        highest_since = 0.0
        setup_just_completed = False

        for i in range(len(df)):
            if i < 4:
                setup_count.append(0)
                setup_complete.append(False)
                setup_bar9_close.append(0.0)
                setup_bar9_range_pct.append(0.0)
                setup_lowest_low.append(0.0)
                bars_since_setup9.append(0)
                highest_close_since_setup9.append(0.0)
                continue

            if df['setup_condition'].iloc[i]:
                count += 1
                if count <= 9:
                    # Track lowest low during setup
                    if count == 1:
                        current_setup_lowest = df['low'].iloc[i]
                    else:
                        current_setup_lowest = min(current_setup_lowest, df['low'].iloc[i])
            else:
                count = 0
                current_setup_lowest = 0.0

            # Check if setup just completed
            if count == 9:
                setup_just_completed = True
                bars_since = 0
                # Calculate bar 9 range position
                bar_range = df['high'].iloc[i] - df['low'].iloc[i]
                if bar_range > 0:
                    current_bar9_range_pct = (df['close'].iloc[i] - df['low'].iloc[i]) / bar_range
                else:
                    current_bar9_range_pct = 0.5
                current_bar9_close = df['close'].iloc[i]
                highest_since = df['close'].iloc[i]
            elif setup_just_completed:
                bars_since += 1
                highest_since = max(highest_since, df['close'].iloc[i])

            setup_count.append(min(count, 9))
            setup_complete.append(count >= 9)
            setup_bar9_close.append(current_bar9_close)
            setup_bar9_range_pct.append(current_bar9_range_pct)
            setup_lowest_low.append(current_setup_lowest)
            bars_since_setup9.append(bars_since)
            highest_close_since_setup9.append(highest_since)

        df['td_setup_count'] = setup_count
        df['td_setup_complete'] = setup_complete
        df['td_setup_bar9_close'] = setup_bar9_close
        df['td_setup_bar9_range_pct'] = setup_bar9_range_pct
        df['td_setup_lowest_low'] = setup_lowest_low
        df['bars_since_setup9'] = bars_since_setup9
        df['highest_close_since_setup9'] = highest_close_since_setup9

        return df

    def calculate_td_countdown_bullish(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Bullish TD Countdown (13-count)

        Starts after Setup 9 completes
        Count bars where: Close >= High[2]
        Track until 13
        """
        df = df.copy()

        if 'td_setup_complete' not in df.columns:
            df = self.calculate_td_setup_bullish(df)

        countdown = []
        countdown_complete = []
        current_countdown = 0
        counting_active = False

        for i in range(len(df)):
            if i < 2:
                countdown.append(0)
                countdown_complete.append(False)
                continue

            # Start countdown after Setup 9
            if df['td_setup_count'].iloc[i] == 9 and (i == 0 or df['td_setup_count'].iloc[i-1] < 9):
                counting_active = True
                current_countdown = 0

            # Count if active and condition met
            if counting_active and current_countdown < 13:
                # Buy Countdown condition: Close >= High[2]
                if df['close'].iloc[i] >= df['high'].iloc[i-2]:
                    current_countdown += 1

            # Reset if new setup starts
            if df['td_setup_count'].iloc[i] == 1 and (i == 0 or df['td_setup_count'].iloc[i-1] != 1):
                counting_active = False
                current_countdown = 0

            countdown.append(current_countdown)
            countdown_complete.append(current_countdown >= 13)

        df['td_countdown'] = countdown
        df['td_countdown_complete'] = countdown_complete

        return df

    def calculate_tdst_support(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate TDST Support level

        TDST Support = Lowest low of bars 1-4 of the bullish TD Setup
        Remains active until close below it
        """
        df = df.copy()

        if 'td_setup_count' not in df.columns:
            df = self.calculate_td_setup_bullish(df)

        tdst_support = []
        tdst_active = []
        current_tdst = 0.0
        is_active = False

        for i in range(len(df)):
            # When setup completes (reaches 9), calculate TDST
            if df['td_setup_count'].iloc[i] == 9 and (i == 0 or df['td_setup_count'].iloc[i-1] < 9):
                # Bars 1-4 of setup are at indices i-8 to i-5
                if i >= 8:
                    setup_start = i - 8
                    setup_bar4 = i - 5
                    # Lowest low of bars 1-4
                    current_tdst = df['low'].iloc[setup_start:setup_bar4+1].min()
                    is_active = True

            # Check for TDST violation (close below support)
            if is_active and df['close'].iloc[i] < current_tdst:
                is_active = False

            tdst_support.append(current_tdst if is_active else 0.0)
            tdst_active.append(is_active)

        df['tdst_support'] = tdst_support
        df['tdst_active'] = tdst_active

        return df

    def calculate_tdst_resistance(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate TDST Resistance level (bearish setup)

        Bearish TD Setup: 9 consecutive bars where Close[n] < Close[n-4]
        TDST Resistance = Highest high of bars 1-4 of the bearish TD Setup
        Remains active until close above it (which signals a breakout)
        """
        df = df.copy()

        # Calculate bearish setup
        df['bearish_setup_condition'] = df['close'] < df['close'].shift(4)

        # Track bearish setup count
        bearish_count = []
        count = 0
        for i in range(len(df)):
            if i < 4:
                bearish_count.append(0)
                continue
            if df['bearish_setup_condition'].iloc[i]:
                count += 1
            else:
                count = 0
            bearish_count.append(min(count, 9))

        df['bearish_setup_count'] = bearish_count

        # Calculate TDST Resistance
        tdst_resistance = []
        tdst_res_active = []
        tdst_res_broken = []
        current_tdst_res = 0.0
        is_res_active = False

        for i in range(len(df)):
            # When bearish setup completes (reaches 9), calculate TDST Resistance
            if df['bearish_setup_count'].iloc[i] == 9 and (i == 0 or df['bearish_setup_count'].iloc[i-1] < 9):
                if i >= 8:
                    setup_start = i - 8
                    setup_bar4 = i - 5
                    # Highest high of bars 1-4
                    current_tdst_res = df['high'].iloc[setup_start:setup_bar4+1].max()
                    is_res_active = True

            # Check for TDST Resistance breakout (close above resistance = bullish)
            res_broken = False
            if is_res_active and df['close'].iloc[i] > current_tdst_res:
                res_broken = True
                is_res_active = False

            tdst_resistance.append(current_tdst_res if is_res_active or res_broken else 0.0)
            tdst_res_active.append(is_res_active)
            tdst_res_broken.append(res_broken)

        df['tdst_resistance'] = tdst_resistance
        df['tdst_res_active'] = tdst_res_active
        df['tdst_res_broken'] = tdst_res_broken

        return df

    def calculate_higher_lows(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Track higher lows for swing structure

        A low is "confirmed" once price moves away by >= 1 bar
        Track the most recent confirmed higher low
        """
        df = df.copy()

        higher_lows = []
        recent_hl = 0.0
        prev_low = 0.0
        potential_hl = 0.0
        bars_since_potential = 0

        for i in range(len(df)):
            current_low = df['low'].iloc[i]

            # Check if we have a potential higher low
            if i > 0:
                if current_low > prev_low and potential_hl == 0:
                    potential_hl = prev_low
                    bars_since_potential = 0
                elif potential_hl > 0:
                    bars_since_potential += 1
                    # Confirm after 1 bar
                    if bars_since_potential >= 1:
                        if potential_hl > recent_hl:
                            recent_hl = potential_hl
                        potential_hl = 0
                        bars_since_potential = 0

            prev_low = current_low
            higher_lows.append(recent_hl)

        df['recent_higher_low'] = higher_lows

        return df

    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all TD indicators

        Args:
            df: DataFrame with OHLC data (columns: open, high, low, close)

        Returns:
            DataFrame with all TD indicator columns
        """
        df = self.calculate_td_ma1_bullish(df)
        df = self.calculate_td_ma2_bullish(df)
        df = self.calculate_td_setup_bullish(df)
        df = self.calculate_td_countdown_bullish(df)
        df = self.calculate_tdst_support(df)
        df = self.calculate_tdst_resistance(df)
        df = self.calculate_higher_lows(df)

        # Combined entry condition: TD MA I AND TD MA II both active
        df['td_entry_valid'] = df['td_ma1_active'] & df['td_ma2_active']

        return df

    def get_current_state(self, df: pd.DataFrame) -> TDState:
        """
        Get current TD indicator state from the last row
        """
        if len(df) == 0:
            return TDState()

        last = df.iloc[-1]

        return TDState(
            td_ma1_active=bool(last.get('td_ma1_active', False)),
            td_ma1_value=float(last.get('td_ma1_value', 0.0)),
            td_ma2_active=bool(last.get('td_ma2_active', False)),
            td_ma2_value=float(last.get('td_ma2_value', 0.0)),
            td_setup_count=int(last.get('td_setup_count', 0)),
            td_setup_complete=bool(last.get('td_setup_complete', False)),
            td_setup_bar9_close=float(last.get('td_setup_bar9_close', 0.0)),
            td_setup_bar9_range_pct=float(last.get('td_setup_bar9_range_pct', 0.0)),
            td_setup_lowest_low=float(last.get('td_setup_lowest_low', 0.0)),
            bars_since_setup9=int(last.get('bars_since_setup9', 0)),
            highest_close_since_setup9=float(last.get('highest_close_since_setup9', 0.0)),
            tdst_support=float(last.get('tdst_support', 0.0)),
            tdst_active=bool(last.get('tdst_active', False)),
            td_countdown=int(last.get('td_countdown', 0)),
            td_countdown_complete=bool(last.get('td_countdown_complete', False)),
            recent_higher_low=float(last.get('recent_higher_low', 0.0))
        )

    def check_tranche1_exit(self, current_close: float, td_state: TDState) -> Tuple[bool, str]:
        """
        Check Tranche 1 exit conditions (30% - de-risk)

        Triggers:
        1. Close < TD MA I value
        2. OR Failed follow-through after Setup 9:
           - No new closing high within 3 bars after bar 9
           - AND (Setup 9 bar closes in lower 50% of range OR next 3 bars close < bar 9 close)
        """
        # Trigger 1: Close below TD MA I
        if td_state.td_ma1_value > 0 and current_close < td_state.td_ma1_value:
            return True, "CLOSE_BELOW_TD_MA1"

        # Trigger 2: Failed follow-through after Setup 9
        if td_state.td_setup_complete and td_state.bars_since_setup9 >= 3:
            # Condition A: No new closing high within 3 bars
            no_expansion = td_state.highest_close_since_setup9 <= td_state.td_setup_bar9_close

            # Condition B: Weak acceptance
            weak_bar9 = td_state.td_setup_bar9_range_pct < 0.5
            closes_below_bar9 = current_close < td_state.td_setup_bar9_close

            if no_expansion and (weak_bar9 or closes_below_bar9):
                return True, "FAILED_FOLLOW_THROUGH"

        return False, ""

    def check_tranche2_exit(self, current_close: float, td_state: TDState,
                           setup_lowest_low: float) -> Tuple[bool, str]:
        """
        Check Tranche 2 exit conditions (45% - structural exit)

        Triggers:
        1. Close < TDST Support
        2. OR Close < lowest low of Setup bars 1-9
        """
        # Trigger 1: Close below TDST
        if td_state.tdst_support > 0 and current_close < td_state.tdst_support:
            return True, "TDST_SUPPORT_BREACH"

        # Trigger 2: Close below Setup validity level
        if setup_lowest_low > 0 and current_close < setup_lowest_low:
            return True, "SETUP_VALIDITY_BREACH"

        return False, ""

    def check_tranche3_exit(self, current_close: float, td_state: TDState,
                           entry_price: float, days_held: int) -> Tuple[bool, str]:
        """
        Check Tranche 3 exit conditions (25% - runner)

        Triggers:
        1. Countdown >= 13 AND Close < TD MA II
        2. OR Higher low break
        3. OR Time stop (20 days or 10 bars after Setup 9)
        """
        # Trigger 1: Countdown exhaustion + TD MA II breach
        if td_state.td_countdown >= 13 and td_state.td_ma2_value > 0:
            if current_close < td_state.td_ma2_value:
                return True, "COUNTDOWN_EXHAUSTION"

        # Trigger 2: Higher low break
        if td_state.recent_higher_low > 0 and current_close < td_state.recent_higher_low:
            return True, "HIGHER_LOW_BREAK"

        # Trigger 3: Time stop
        # 20 trading days from entry OR 10 bars after Setup 9
        time_limit = max(20, td_state.bars_since_setup9 + 10) if td_state.td_setup_complete else 20
        if days_held >= time_limit:
            # Check if we've advanced at least 1R (simple check: price > entry)
            # and no new setup formed
            if current_close <= entry_price and not td_state.td_setup_complete:
                return True, "TIME_STOP"

        return False, ""


def test_td_indicators():
    """Test TD indicator calculations with sample data"""
    import numpy as np

    # Create sample uptrend data
    np.random.seed(42)
    n = 60
    base = 100
    trend = np.cumsum(np.random.randn(n) * 0.5 + 0.3)

    df = pd.DataFrame({
        'open': base + trend + np.random.randn(n) * 0.5,
        'high': base + trend + np.abs(np.random.randn(n)) * 1.5,
        'low': base + trend - np.abs(np.random.randn(n)) * 1.5,
        'close': base + trend + np.random.randn(n) * 0.5
    })

    calc = TDIndicatorCalculator()
    result = calc.calculate_all(df)

    print("TD Indicator Test Results:")
    print(f"TD MA I Active days: {result['td_ma1_active'].sum()}")
    print(f"TD MA II Active days: {result['td_ma2_active'].sum()}")
    print(f"TD Setup Complete days: {result['td_setup_complete'].sum()}")
    print(f"TD Countdown >= 13: {(result['td_countdown'] >= 13).sum()}")
    print(f"TDST Active days: {result['tdst_active'].sum()}")
    print(f"Entry Valid days: {result['td_entry_valid'].sum()}")

    state = calc.get_current_state(result)
    print(f"\nCurrent State:")
    print(f"  TD MA I: {'Active' if state.td_ma1_active else 'Inactive'} @ {state.td_ma1_value:.2f}")
    print(f"  TD MA II: {'Active' if state.td_ma2_active else 'Inactive'} @ {state.td_ma2_value:.2f}")
    print(f"  TD Setup: {state.td_setup_count}/9")
    print(f"  TD Countdown: {state.td_countdown}/13")
    print(f"  TDST Support: {state.tdst_support:.2f} ({'Active' if state.tdst_active else 'Inactive'})")
    print(f"  Setup Lowest Low: {state.td_setup_lowest_low:.2f}")
    print(f"  Recent Higher Low: {state.recent_higher_low:.2f}")

    return result


if __name__ == "__main__":
    test_td_indicators()
