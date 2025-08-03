# Dashboard Configuration Guide

## Overview
The Market Regime Dashboard at port 8080 now supports configurable modules through the `config.ini` file. You can enable/disable specific sections based on your needs.

## Configuration Location
Edit `/Users/maverick/PycharmProjects/India-TS/Daily/config.ini` and look for the `[Dashboard]` section.

## Available Modules

### Currently Enabled (set to true)
- `show_ml_insights` - ML-based strategy recommendations
- `show_market_regime` - Current market regime analysis
- `show_sma_breadth` - SMA breadth charts and analysis
- `show_volume_breadth` - Volume breadth analysis
- `show_reversal_patterns` - Reversal pattern statistics
- `show_g_pattern` - G Pattern analysis
- `show_vsr_tracker` - VSR tracker section
- `show_optimal_conditions` - Optimal trading conditions display

### Currently Disabled (set to false)
- `show_momentum_scanner` - Momentum Scanner Analysis section
- `show_regime_history` - Regime History chart
- `show_confidence_trend` - Confidence Trend chart
- `show_weekly_bias` - Weekly Market Bias section

## How to Change Configuration

1. Edit the config file:
```bash
nano /Users/maverick/PycharmProjects/India-TS/Daily/config.ini
```

2. Find the `[Dashboard]` section and change any value from `true` to `false` or vice versa:
```ini
[Dashboard]
# Dashboard module configuration - set to true/false to enable/disable
show_ml_insights = true
show_momentum_scanner = false  # Change to true to enable
...
```

3. Save the file and restart the dashboard for changes to take effect.

## Implementation Details

### Frontend (HTML/JavaScript)
- Uses Jinja2 templating with `{% if config.show_module_name %}` conditionals
- JavaScript checks `dashboardConfig.show_module_name` before initializing features
- Charts are only created if their corresponding module is enabled

### Backend (Python)
- Configuration is loaded from `config.ini` using `configparser`
- Settings are passed to the template as the `config` object
- Default values are provided for backward compatibility

## Benefits
1. **Performance**: Disabled modules don't consume resources
2. **Customization**: Users can focus on relevant metrics
3. **Clean UI**: Hide unused sections for better clarity
4. **Easy Management**: No code changes needed to toggle features

## Troubleshooting
- If a section doesn't appear/disappear after changing config, ensure you've restarted the dashboard
- Check the console logs for any JavaScript errors
- Verify the config.ini syntax is correct (true/false, not True/False)