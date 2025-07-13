#!/bin/bash
# Daily Portfolio Regime Check
# Run this script every morning before market open

echo "======================================"
echo "Daily Portfolio Regime Analysis"
echo "Date: $(date '+%A, %B %d, %Y')"
echo "======================================"
echo ""

# Navigate to project directory
cd /Users/maverick/PycharmProjects/India-TS

# Run the portfolio analysis
python3 ML-Framework/scripts/analyze_my_portfolio.py

# Optional: Open the latest report
echo ""
echo "Analysis complete!"
echo ""
echo "To view detailed reports, check:"
echo "ML-Framework/results/portfolio_analysis/"