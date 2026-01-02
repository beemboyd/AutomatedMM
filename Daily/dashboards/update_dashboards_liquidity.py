#!/usr/bin/env python3
"""
Update All Dashboards with Liquidity Display
Adds liquidity widget integration to all dashboard templates
"""

import os
import re
import shutil
from datetime import datetime

# Dashboard templates to update
TEMPLATES = [
    'hourly_tracker_dashboard.html',
    'hourly_short_tracker_dashboard.html',
    'short_momentum_dashboard.html'
]

TEMPLATE_DIR = '/Users/maverick/PycharmProjects/India-TS/Daily/dashboards/templates/'

def backup_template(template_path):
    """Create backup of template before modifying"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{template_path}.backup_{timestamp}"
    shutil.copy2(template_path, backup_path)
    print(f"✓ Backed up {os.path.basename(template_path)} to {os.path.basename(backup_path)}")
    return backup_path

def add_liquidity_script(template_path):
    """Add liquidity widget script to template"""
    with open(template_path, 'r') as f:
        content = f.read()
    
    # Check if already added
    if 'liquidity-widget.js' in content:
        print(f"  ⚠ Liquidity widget already added to {os.path.basename(template_path)}")
        return False
    
    # Add script tag before closing body tag
    script_tag = '\n    <script src="/static/liquidity-widget.js"></script>\n'
    
    # Find </body> tag
    body_close = content.rfind('</body>')
    if body_close == -1:
        print(f"  ✗ Could not find </body> tag in {os.path.basename(template_path)}")
        return False
    
    # Insert script tag
    content = content[:body_close] + script_tag + content[body_close:]
    
    with open(template_path, 'w') as f:
        f.write(content)
    
    print(f"  ✓ Added liquidity widget script to {os.path.basename(template_path)}")
    return True

def add_liquidity_display_example(template_path):
    """Add example liquidity display code to template"""
    example_code = """
    <!-- Liquidity Display Example -->
    <script>
    // Example: Add liquidity info to ticker displays
    async function enhanceWithLiquidity(tickerElement, ticker) {
        const liquidityData = await window.liquidityWidget.fetchLiquidityData(ticker);
        if (liquidityData) {
            // Add simple badge
            const badge = window.liquidityWidget.createSimpleBadge(liquidityData);
            tickerElement.insertAdjacentHTML('beforeend', badge);
            
            // Or add detailed card (for expanded views)
            // const card = window.liquidityWidget.createDetailedCard(liquidityData);
            // tickerElement.insertAdjacentHTML('afterend', card);
        }
    }
    
    // Call this when displaying tickers
    // enhanceWithLiquidity(element, 'RELIANCE');
    </script>
    """
    
    with open(template_path, 'r') as f:
        content = f.read()
    
    # Check if example already added
    if 'enhanceWithLiquidity' in content:
        print(f"  ⚠ Liquidity display example already in {os.path.basename(template_path)}")
        return False
    
    # Add before closing body
    body_close = content.rfind('</body>')
    if body_close == -1:
        return False
    
    content = content[:body_close] + example_code + '\n' + content[body_close:]
    
    with open(template_path, 'w') as f:
        f.write(content)
    
    print(f"  ✓ Added liquidity display example to {os.path.basename(template_path)}")
    return True

def update_flask_app_static_route():
    """Ensure Flask apps serve static files"""
    dashboard_files = [
        'hourly_tracker_dashboard.py',
        'hourly_short_tracker_dashboard.py', 
        'short_momentum_dashboard.py'
    ]
    
    for dash_file in dashboard_files:
        dash_path = os.path.join('/Users/maverick/PycharmProjects/India-TS/Daily/dashboards/', dash_file)
        if not os.path.exists(dash_path):
            continue
            
        with open(dash_path, 'r') as f:
            content = f.read()
        
        # Check if static folder is configured
        if 'static_folder' not in content and 'Flask(__name__' in content:
            # Update Flask initialization
            content = content.replace(
                'app = Flask(__name__)',
                "app = Flask(__name__, static_folder='static', static_url_path='/static')"
            )
            
            with open(dash_path, 'w') as f:
                f.write(content)
            
            print(f"✓ Updated {dash_file} to serve static files")

def main():
    print("🚀 Updating Dashboards with Liquidity Display")
    print("=" * 50)
    
    # Ensure static directory exists
    static_dir = os.path.join(TEMPLATE_DIR, '..', 'static')
    os.makedirs(static_dir, exist_ok=True)
    print(f"✓ Static directory ready: {static_dir}")
    
    # Update Flask apps to serve static files
    print("\n📝 Updating Flask applications...")
    update_flask_app_static_route()
    
    # Process each template
    print("\n📝 Processing templates...")
    for template_name in TEMPLATES:
        template_path = os.path.join(TEMPLATE_DIR, template_name)
        
        if not os.path.exists(template_path):
            print(f"✗ Template not found: {template_name}")
            continue
        
        print(f"\nProcessing {template_name}:")
        
        # Backup first
        backup_template(template_path)
        
        # Add liquidity script
        add_liquidity_script(template_path)
        
        # Add example code
        add_liquidity_display_example(template_path)
    
    print("\n" + "=" * 50)
    print("✅ Dashboard update complete!")
    print("\nNext steps:")
    print("1. Restart dashboard services to apply changes")
    print("2. Liquidity API should be running on port 5555")
    print("3. Test liquidity display on each dashboard")
    print("\nLiquidity widget methods available:")
    print("  - window.liquidityWidget.fetchLiquidityData(ticker)")
    print("  - window.liquidityWidget.createSimpleBadge(data)")
    print("  - window.liquidityWidget.createDetailedCard(data)")
    print("  - window.liquidityWidget.createInlineInfo(data)")

if __name__ == '__main__':
    main()