#!/usr/bin/env python3
"""
Update G Pattern section in the market regime dashboard
"""

import os
import re
from datetime import datetime

def read_g_pattern_summary():
    """Read and parse G Pattern Summary file"""
    summary_file = "/Users/maverick/PycharmProjects/India-TS/Daily/G_Pattern_Master/G_Pattern_Summary.txt"
    
    if not os.path.exists(summary_file):
        return None
        
    categories = {
        'G_PATTERN_CONFIRMED': [],
        'PATTERN_EMERGING': [],
        'WATCH_CLOSELY': []
    }
    
    current_category = None
    
    with open(summary_file, 'r') as f:
        lines = f.readlines()
        
    for line in lines:
        line = line.strip()
        
        if "G PATTERN CONFIRMED - FULL POSITION (100%)" in line:
            current_category = 'G_PATTERN_CONFIRMED'
        elif "PATTERN EMERGING - INITIAL POSITION (25%)" in line:
            current_category = 'PATTERN_EMERGING'
        elif "WATCH CLOSELY - PRE-ENTRY" in line:
            current_category = 'WATCH_CLOSELY'
        elif "WATCH ONLY" in line:
            break  # Stop at WATCH ONLY
        elif current_category and line and not line.startswith("-"):
            if ":" in line and "Score" in line:
                # Extract ticker and score
                match = re.match(r'(\w+)\s*\([^)]*\):\s*Score\s*(\d+)', line)
                if match:
                    ticker = match.group(1)
                    score = match.group(2)
                    categories[current_category].append((ticker, score))
    
    return categories

def update_dashboard_g_pattern(categories):
    """Update the G Pattern section in the dashboard HTML"""
    dashboard_file = "/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/dashboards/market_regime_dashboard.html"
    
    if not os.path.exists(dashboard_file):
        print(f"Dashboard file not found: {dashboard_file}")
        return
        
    # Read current dashboard
    with open(dashboard_file, 'r') as f:
        content = f.read()
    
    # Update G Pattern Confirmed count and stocks
    confirmed = categories['G_PATTERN_CONFIRMED']
    confirmed_html = f"""<div style="font-size: 2em; font-weight: bold; color: #27ae60;">{len(confirmed)}</div>
                    <div style="color: #555; margin: 10px 0;">Ready for Full Position (100%)</div>
                    <div style="font-size: 0.9em; color: #666;">"""
    
    for ticker, score in confirmed[:3]:  # Show top 3
        confirmed_html += f"\n                        <div>• {ticker} (Score: {score})</div>"
    confirmed_html += "\n                    </div>"
    
    # Update Pattern Emerging count and stocks
    emerging = categories['PATTERN_EMERGING']
    emerging_html = f"""<div style="font-size: 2em; font-weight: bold; color: #3498db;">{len(emerging)}</div>
                    <div style="color: #555; margin: 10px 0;">Initial Position (25%)</div>
                    <div style="font-size: 0.9em; color: #666;">"""
    
    for ticker, score in emerging[:3]:  # Show top 3
        emerging_html += f"\n                        <div>• {ticker} (Score: {score})</div>"
    emerging_html += "\n                    </div>"
    
    # Update Watch Closely count and stocks
    watch = categories['WATCH_CLOSELY']
    watch_html = f"""<div style="font-size: 2em; font-weight: bold; color: #f39c12;">{len(watch)}</div>
                    <div style="color: #555; margin: 10px 0;">Pre-Entry Monitoring</div>
                    <div style="font-size: 0.9em; color: #666;">
                        <div>Top 3 by Score:</div>"""
    
    for ticker, score in watch[:3]:  # Show top 3
        watch_html += f"\n                        <div>• {ticker} (Score: {score})</div>"
    watch_html += "\n                    </div>"
    
    # Update HTML with regex to preserve structure
    # Update Confirmed section
    content = re.sub(
        r'<h3 style="color: #27ae60[^"]*">G PATTERN CONFIRMED</h3>.*?</div>\s*</div>',
        f'<h3 style="color: #27ae60; margin-bottom: 10px;">G PATTERN CONFIRMED</h3>\n                    {confirmed_html}\n                </div>',
        content,
        flags=re.DOTALL
    )
    
    # Update Emerging section
    content = re.sub(
        r'<h3 style="color: #3498db[^"]*">PATTERN EMERGING</h3>.*?</div>\s*</div>',
        f'<h3 style="color: #3498db; margin-bottom: 10px;">PATTERN EMERGING</h3>\n                    {emerging_html}\n                </div>',
        content,
        flags=re.DOTALL
    )
    
    # Update Watch section
    content = re.sub(
        r'<h3 style="color: #f39c12[^"]*">WATCH CLOSELY</h3>.*?</div>\s*</div>',
        f'<h3 style="color: #f39c12; margin-bottom: 10px;">WATCH CLOSELY</h3>\n                    {watch_html}\n                </div>',
        content,
        flags=re.DOTALL
    )
    
    # Update capital deployment based on config.ini
    import configparser
    config_path = "/Users/maverick/PycharmProjects/India-TS/Daily/config.ini"
    config = configparser.ConfigParser()
    config.read(config_path)
    deployment_percent = config.get('DEFAULT', 'capital_deployment_percent', fallback='25.0')
    
    # Update deployment text
    content = re.sub(
        r'<span style="color: #3498db;">\d+% allocated to \d+ PATTERN EMERGING stocks</span>',
        f'<span style="color: #3498db;">{deployment_percent}% allocated to {len(emerging)} PATTERN EMERGING stocks</span>',
        content
    )
    
    # Write updated content
    with open(dashboard_file, 'w') as f:
        f.write(content)
    
    print(f"Dashboard updated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  - G Pattern Confirmed: {len(confirmed)} stocks")
    print(f"  - Pattern Emerging: {len(emerging)} stocks")
    print(f"  - Watch Closely: {len(watch)} stocks")

if __name__ == "__main__":
    categories = read_g_pattern_summary()
    if categories:
        update_dashboard_g_pattern(categories)
    else:
        print("Could not read G Pattern Summary file")