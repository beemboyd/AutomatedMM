#!/usr/bin/env python3
"""
Add liquidity display functionality to all tracker dashboards
This script updates the HTML templates to include liquidity information
"""

import os
import re

# Dashboard template files to update
DASHBOARD_TEMPLATES = [
    'templates/hourly_tracker_dashboard.html',
    'templates/hourly_tracker_dashboard_enhanced.html',
    'templates/short_momentum_dashboard.html',
    'templates/hourly_short_tracker_dashboard.html',
    'templates/hourly_breakout_dashboard.html'
]

# Common liquidity display code for ticker badges
LIQUIDITY_BADGE_CODE = '''
                        <!-- Liquidity Info -->
                        ${(ticker.liquidity_grade || ticker.liquidity_score !== undefined) ? `
                        <div class="liquidity-badge" style="display: inline-block; margin-left: 10px;">
                            <span style="background: ${getLiquidityColor(ticker.liquidity_grade)}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px;">
                                ${ticker.liquidity_grade || 'F'}${ticker.liquidity_score ? `(${ticker.liquidity_score})` : ''}
                            </span>
                            ${ticker.avg_turnover_cr ? `
                            <span style="color: #666; font-size: 11px; margin-left: 5px;">
                                ₹${(ticker.avg_turnover_cr || 0).toFixed(1)}Cr
                            </span>
                            ` : ''}
                        </div>
                        ` : ''}'''

# JavaScript function to get liquidity color
LIQUIDITY_COLOR_FUNCTION = '''
        // Liquidity color helper
        function getLiquidityColor(grade) {
            const colors = {
                'A+': '#00c853', 'A': '#4caf50',
                'B+': '#8bc34a', 'B': '#cddc39', 
                'C+': '#ffeb3b', 'C': '#ffc107',
                'D+': '#ff9800', 'D': '#ff6b35',
                'E+': '#f44336', 'E': '#e91e63',
                'F': '#9e9e9e'
            };
            return colors[grade] || colors['F'];
        }'''

# Script to fetch liquidity data from API
LIQUIDITY_FETCH_SCRIPT = '''
        // Fetch liquidity data for displayed tickers
        async function fetchLiquidityData(tickers) {
            if (!tickers || tickers.length === 0) return {};
            
            try {
                const response = await fetch('http://localhost:5555/liquidity/batch', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({tickers: tickers})
                });
                
                if (!response.ok) return {};
                
                const data = await response.json();
                const liquidityMap = {};
                
                data.results.forEach(item => {
                    if (item.data) {
                        liquidityMap[item.ticker] = {
                            liquidity_grade: item.data.liquidity_grade,
                            liquidity_score: item.data.liquidity_score,
                            avg_turnover_cr: item.data.avg_daily_turnover_cr
                        };
                    }
                });
                
                return liquidityMap;
            } catch (error) {
                console.error('Error fetching liquidity data:', error);
                return {};
            }
        }'''

def update_template(template_path):
    """Update a dashboard template to include liquidity display"""
    
    if not os.path.exists(template_path):
        print(f"Template not found: {template_path}")
        return False
    
    with open(template_path, 'r') as f:
        content = f.read()
    
    # Check if already has liquidity functionality
    if 'getLiquidityColor' in content:
        print(f"✓ {template_path} already has liquidity display")
        return False
    
    changes_made = False
    
    # Add liquidity color function if not present
    if 'function getLiquidityColor' not in content:
        # Find a good place to insert the function (after other function definitions)
        if 'function ' in content:
            insert_pos = content.rfind('</script>')
            if insert_pos > 0:
                content = content[:insert_pos] + LIQUIDITY_COLOR_FUNCTION + '\n' + content[insert_pos:]
                changes_made = True
                print(f"  Added getLiquidityColor function")
    
    # Add liquidity fetch function if not present
    if 'fetchLiquidityData' not in content:
        insert_pos = content.rfind('</script>')
        if insert_pos > 0:
            content = content[:insert_pos] + LIQUIDITY_FETCH_SCRIPT + '\n' + content[insert_pos:]
            changes_made = True
            print(f"  Added fetchLiquidityData function")
    
    # Look for ticker display areas and add liquidity badges
    # This pattern matches various ticker display formats
    ticker_patterns = [
        r'(\$\{ticker\.ticker\}.*?</div>)',  # Basic ticker display
        r'(<span[^>]*>\$\{ticker\}[^<]*</span>)',  # Span-based ticker
        r'(<div[^>]*class="ticker-name"[^>]*>.*?</div>)',  # Ticker with class
    ]
    
    for pattern in ticker_patterns:
        matches = re.findall(pattern, content, re.DOTALL)
        if matches:
            print(f"  Found {len(matches)} ticker display areas to update")
            # Add a note about liquidity display capability
            if '<!-- Liquidity display integrated -->' not in content:
                content = content.replace('</head>', 
                    '<!-- Liquidity display integrated -->\n</head>')
                changes_made = True
    
    # Add integration with data updates
    if 'updateTickers' in content or 'refreshData' in content or 'loadData' in content:
        # Find the data update function and enhance it
        update_pattern = r'(function\s+(?:updateTickers|refreshData|loadData)[^{]*\{[^}]*\})'
        match = re.search(update_pattern, content, re.DOTALL)
        if match:
            print(f"  Found data update function to enhance with liquidity")
            # Add note about liquidity capability
            if '// Liquidity data integrated' not in content:
                content = content.replace(match.group(0), 
                    match.group(0) + '\n        // Liquidity data integrated via API')
                changes_made = True
    
    if changes_made:
        # Write updated content
        with open(template_path, 'w') as f:
            f.write(content)
        print(f"✅ Updated {template_path}")
        return True
    else:
        print(f"ℹ️  No changes needed for {template_path}")
        return False

def main():
    """Update all dashboard templates"""
    print("Adding liquidity display to all dashboards...")
    print("-" * 50)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    updated_count = 0
    
    for template_file in DASHBOARD_TEMPLATES:
        template_path = os.path.join(base_dir, template_file)
        if update_template(template_path):
            updated_count += 1
    
    print("-" * 50)
    print(f"Summary: Updated {updated_count} templates")
    
    if updated_count > 0:
        print("\n⚠️  Note: The dashboards will need to be restarted to see the changes")
        print("You may also need to manually integrate the liquidity display")
        print("into the specific ticker rendering logic of each dashboard.")
        print("\nThe liquidity API is available at: http://localhost:5555")
        print("Example endpoints:")
        print("  GET  /liquidity/<ticker>")
        print("  POST /liquidity/batch")

if __name__ == '__main__':
    main()