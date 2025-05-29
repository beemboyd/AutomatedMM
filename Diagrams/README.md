# System Documentation

This directory contains detailed documentation on the trading system's architecture, components, and processes.

## Available Diagrams

1. **[System Overview](system_overview.md)**  
   High-level architecture and component relationships within the trading system.

2. **[Market Scanning Process](scan_market_flow.md)**  
   Detailed flow of how scan_market.py identifies trading opportunities.

3. **[Order Placement Process](place_orders_flow.md)**  
   Step-by-step execution of place_orders.py and how it handles trading signals.

4. **[Position Watchdog Flow](position_watchdog_flow.md)**  
   Position monitoring and stop loss management by position_watchdog.py.

5. **[System State Management](system_state_flow.md)**  
   State tracking, persistence, and synchronization across system components.

6. **[Common Issues and Solutions](common_issues.md)**  
   Documentation of known issues and their fixes.

## How to Use These Diagrams

These diagrams are written in Markdown with embedded Mermaid flowchart syntax. To view them with rendered diagrams:

1. **GitHub Viewing**: 
   - GitHub natively renders Mermaid diagrams in Markdown files
   - Simply open the MD files in the GitHub web interface

2. **VSCode Viewing**:
   - Install the "Markdown Preview Mermaid Support" extension
   - Open the MD file and use the "Markdown: Open Preview" command

3. **Local HTML Rendering**:
   - Use a tool like `grip` to render locally:
   ```
   pip install grip
   grip system_overview.md
   ```

## Keeping Documentation Updated

1. **When Making System Changes**:
   - Update relevant diagrams to reflect new processes
   - Document changes in the CLAUDE.md file with date stamps
   - Update the "Common Issues" document if fixing known problems

2. **Reviewing Documentation**:
   - Review these diagrams periodically to ensure accuracy
   - Use diagrams as reference when debugging system issues
   - Refer to diagrams when onboarding new developers

## Frequently Asked Questions

**Q: When should I use place_orders.py vs. position_watchdog.py?**  
A: place_orders.py is ONLY for placing new orders based on signal files. position_watchdog.py handles monitoring positions and executing stop losses.

**Q: How does position closing work?**  
A: Positions are ONLY closed by:
1. position_watchdog.py when stop loss levels are hit
2. End-of-day automatic closure by Zerodha for MIS positions

**Q: How do I monitor the system's state?**  
A: The system's state is stored in trading_state.json and can be monitored through the logs of each component. Each component writes detailed logs with timestamps.

**Q: How are trading signals generated?**  
A: scan_market.py analyzes price data using technical indicators (EMA, ATR, Keltner Channels) to identify potential trading opportunities, which are then saved to Excel signal files for consumption by place_orders.py.