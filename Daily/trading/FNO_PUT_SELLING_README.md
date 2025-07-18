# FNO Put Option Selling Scripts

This directory contains scripts for selling put options based on KC Upper Limit Trending FNO scanner results.

## Scripts

### 1. place_orders_FNO.py (Basic Version)
- Simple put selling script with basic functionality
- Uses estimated premiums and simplified margin calculations
- Good for testing and understanding the workflow

### 2. place_orders_FNO_advanced.py (Advanced Version)
- More sophisticated implementation
- Includes proper margin calculations
- Better strike selection logic
- Detailed risk analysis display
- Support for both weekly and monthly expiries

## How It Works

1. **Reads Scanner Results**: Looks for the latest `KC_Upper_Limit_Trending_FNO_*.xlsx` file in `/Daily/FNO/Long/`
2. **Selects Top Tickers**: Takes the top 2 ranked tickers from the scanner
3. **Capital Allocation**: Allocates 2% of available capital, split equally between the 2 tickers
4. **Strike Selection**: Selects put strikes approximately 5-8% OTM (out of the money)
5. **Order Confirmation**: Shows detailed analysis and asks for user confirmation
6. **Order Placement**: Places SELL orders for put options

## Usage

### Basic Version:
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/trading
python3 place_orders_FNO.py
```

### Advanced Version:
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/trading
python3 place_orders_FNO_advanced.py
```

## Key Features

- **Multi-user Support**: Select which account to use
- **Risk Management**: Only allocates 2% of capital
- **Safety Checks**: Requires user confirmation before placing orders
- **Detailed Analysis**: Shows premium, margin, and risk calculations
- **Logging**: Creates detailed logs in `/Daily/logs/<username>/`

## Risk Warning

⚠️ **IMPORTANT**: Put selling involves significant risk:
- Unlimited downside if the stock falls significantly
- Requires margin and can lead to margin calls
- Options are leveraged instruments
- Only trade if you understand the risks

## Configuration

The scripts use the standard `config.ini` file for API credentials. Ensure your credentials are properly configured:

```ini
[API_CREDENTIALS_YourName]
api_key = your_api_key
api_secret = your_api_secret
access_token = your_access_token
```

## FNO Lot Sizes

The advanced script includes lot sizes for major FNO stocks. In production, these should be fetched dynamically from NSE as they can change.

## Example Output

```
=== Advanced FNO Put Option Selling Script ===

Top 2 FNO tickers for put selling:
  RELIANCE: Rank 1, Score 95.5, Close ₹2850.00
  TCS: Rank 2, Score 92.3, Close ₹3650.00

Available capital: ₹500,000.00
Total allocation (2%): ₹10,000.00
Capital per ticker: ₹5,000.00

OPTION ANALYSIS: RELIANCE
============================================================
Underlying Price: ₹2,850.00
Strike Selected: ₹2,675.00
OTM %: 6.14%
Premium per unit: ₹15.50
Total Premium: ₹3,875.00
Margin per lot: ₹45,000.00
Return on Margin: 8.61%
```

## Important Notes

1. **Test First**: Always test with small quantities first
2. **Market Hours**: Options can only be traded during market hours
3. **Liquidity**: Ensure the strikes you're selling have good liquidity
4. **Exit Strategy**: Have a clear exit strategy before entering trades
5. **Monitor Positions**: Regularly monitor your short option positions

## Support

For issues or questions, check the logs in `/Daily/logs/<username>/` for detailed error messages.