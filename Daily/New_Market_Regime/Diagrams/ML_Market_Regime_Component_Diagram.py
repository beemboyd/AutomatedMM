#!/usr/bin/env python3
"""
Generate ML Market Regime System Component Diagram
Creates a visual representation of the system architecture
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.lines as mlines

# Create figure and axis
fig, ax = plt.subplots(1, 1, figsize=(16, 12))
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis('off')

# Title
ax.text(5, 9.5, 'ML Market Regime Prediction System - Component Architecture', 
        fontsize=16, fontweight='bold', ha='center')

# Color scheme
colors = {
    'ui': '#E8F4FD',      # Light blue for UI
    'api': '#B8E0FF',     # Medium blue for API
    'logic': '#7FC4FD',   # Darker blue for logic
    'model': '#FFE4B5',   # Light orange for ML models
    'data': '#98FB98',    # Light green for data
    'jobs': '#FFB6C1'     # Light pink for jobs
}

# Function to create a component box
def create_component(ax, x, y, width, height, label, sublabel='', color='#E8F4FD'):
    box = FancyBboxPatch((x, y), width, height,
                         boxstyle="round,pad=0.02",
                         linewidth=1, edgecolor='black',
                         facecolor=color)
    ax.add_patch(box)
    
    # Add text
    ax.text(x + width/2, y + height/2 + 0.05, label,
           fontsize=10, fontweight='bold', ha='center', va='center')
    if sublabel:
        ax.text(x + width/2, y + height/2 - 0.1, sublabel,
               fontsize=8, ha='center', va='center', style='italic')
    
    return box

# Function to create an arrow
def create_arrow(ax, x1, y1, x2, y2, label='', style='->'):
    arrow = FancyArrowPatch((x1, y1), (x2, y2),
                           connectionstyle="arc3,rad=0", 
                           arrowstyle=style,
                           linewidth=1.5, color='black')
    ax.add_patch(arrow)
    
    if label:
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        ax.text(mid_x, mid_y, label, fontsize=8, ha='center',
               bbox=dict(boxstyle="round,pad=0.3", facecolor='white', edgecolor='none', alpha=0.8))

# Layer 1: User Interface Components
ui_y = 7.5
create_component(ax, 0.5, ui_y, 1.8, 0.8, 'Enhanced Dashboard', 'Port: 8080', colors['ui'])
create_component(ax, 2.6, ui_y, 1.8, 0.8, 'ML Monitoring', 'Port: 8082', colors['ui'])
create_component(ax, 4.7, ui_y, 1.8, 0.8, 'API Clients', 'Direct Access', colors['ui'])
create_component(ax, 6.8, ui_y, 1.8, 0.8, 'Test Scripts', 'Integration Tests', colors['ui'])

# Layer 2: API Layer
api_y = 6
create_component(ax, 1.5, api_y, 2.5, 0.8, 'ML Prediction API', 'Port: 8083', colors['api'])
create_component(ax, 4.5, api_y, 2, 0.8, 'Dashboard APIs', 'REST Endpoints', colors['api'])
create_component(ax, 7, api_y, 1.5, 0.8, 'Integration Module', 'ml_integration_new', colors['api'])

# Layer 3: Business Logic
logic_y = 4.5
create_component(ax, 0.8, logic_y, 2, 0.8, 'MarketRegimePredictor', 'Main Class', colors['logic'])
create_component(ax, 3, logic_y, 2, 0.8, 'Feature Engineering', '22 Features', colors['logic'])
create_component(ax, 5.2, logic_y, 2, 0.8, 'Model Loader', 'Model Management', colors['logic'])
create_component(ax, 7.4, logic_y, 1.8, 0.8, 'Data Validator', 'Quality Checks', colors['logic'])

# Layer 4: ML Models
model_y = 3
create_component(ax, 1, model_y, 2.5, 0.8, 'Gradient Boosting', 'v20250909_133414', colors['model'])
create_component(ax, 3.8, model_y, 1.8, 0.8, 'StandardScaler', 'Feature Scaling', colors['model'])
create_component(ax, 6, model_y, 1.8, 0.8, 'Model Metadata', 'JSON Config', colors['model'])

# Layer 5: Data Sources
data_y = 1.5
create_component(ax, 0.5, data_y, 2, 0.8, 'Analysis DB', 'market_data.db', colors['data'])
create_component(ax, 2.8, data_y, 2, 0.8, 'ML Regime DB', 'ml_market_regime.db', colors['data'])
create_component(ax, 5.1, data_y, 2, 0.8, 'Zerodha API', 'Real-time Data', colors['data'])
create_component(ax, 7.4, data_y, 1.8, 0.8, 'Cache Layer', 'Redis/Memory', colors['data'])

# Layer 6: Scheduled Jobs
jobs_y = 0.2
create_component(ax, 1, jobs_y, 2, 0.6, 'Data Collection', '9AM, 4PM', colors['jobs'])
create_component(ax, 3.5, jobs_y, 2, 0.6, 'Model Retrain', 'Weekly', colors['jobs'])
create_component(ax, 6, jobs_y, 2, 0.6, 'Data Ingestor', 'Hourly', colors['jobs'])

# Add arrows showing data flow
# UI to API
create_arrow(ax, 1.4, ui_y, 2.2, api_y + 0.8, 'HTTP')
create_arrow(ax, 3.5, ui_y, 3.5, api_y + 0.8, 'AJAX')
create_arrow(ax, 5.6, ui_y, 5.5, api_y + 0.8)

# API to Logic
create_arrow(ax, 2.75, api_y, 1.8, logic_y + 0.8, 'predict()')
create_arrow(ax, 3.5, api_y, 4, logic_y + 0.8, 'features')
create_arrow(ax, 5.5, api_y, 6.2, logic_y + 0.8, 'load')

# Logic to Models
create_arrow(ax, 1.8, logic_y, 2.25, model_y + 0.8, 'inference')
create_arrow(ax, 4, logic_y, 4.7, model_y + 0.8, 'scale')
create_arrow(ax, 6.2, logic_y, 6.9, model_y + 0.8, 'config')

# Models to Data
create_arrow(ax, 2.25, model_y, 1.5, data_y + 0.8, 'query')
create_arrow(ax, 4.7, model_y, 3.8, data_y + 0.8, 'fetch')
create_arrow(ax, 6.9, model_y, 6.1, data_y + 0.8, 'stream')

# Jobs to Data
create_arrow(ax, 2, jobs_y + 0.6, 1.5, data_y, 'collect')
create_arrow(ax, 4.5, jobs_y + 0.6, 3.8, data_y, 'store')
create_arrow(ax, 7, jobs_y + 0.6, 8.3, data_y, 'ingest')

# Add legend
legend_elements = [
    mpatches.Patch(color=colors['ui'], label='User Interface'),
    mpatches.Patch(color=colors['api'], label='API Layer'),
    mpatches.Patch(color=colors['logic'], label='Business Logic'),
    mpatches.Patch(color=colors['model'], label='ML Models'),
    mpatches.Patch(color=colors['data'], label='Data Sources'),
    mpatches.Patch(color=colors['jobs'], label='Scheduled Jobs')
]
ax.legend(handles=legend_elements, loc='upper right', fontsize=9)

# Add key metrics box
metrics_box = FancyBboxPatch((8.5, 8.5), 1.3, 1, 
                            boxstyle="round,pad=0.02",
                            linewidth=1, edgecolor='black',
                            facecolor='white')
ax.add_patch(metrics_box)
ax.text(9.15, 9.3, 'System Metrics', fontsize=10, fontweight='bold', ha='center')
ax.text(9.15, 9.1, '22 Features', fontsize=8, ha='center')
ax.text(9.15, 8.95, '3 Regimes', fontsize=8, ha='center')
ax.text(9.15, 8.8, '<100ms Latency', fontsize=8, ha='center')
ax.text(9.15, 8.65, '100% Accuracy', fontsize=8, ha='center')

# Add ports info box
ports_box = FancyBboxPatch((8.5, 3.5), 1.3, 1.5, 
                          boxstyle="round,pad=0.02",
                          linewidth=1, edgecolor='black',
                          facecolor='#F0F0F0')
ax.add_patch(ports_box)
ax.text(9.15, 4.7, 'Service Ports', fontsize=10, fontweight='bold', ha='center')
ax.text(9.15, 4.45, '8080: Main Dashboard', fontsize=7, ha='center')
ax.text(9.15, 4.25, '8082: ML Monitor', fontsize=7, ha='center')
ax.text(9.15, 4.05, '8083: ML API', fontsize=7, ha='center')
ax.text(9.15, 3.85, '3002: Hourly Tracker', fontsize=7, ha='center')
ax.text(9.15, 3.65, '5432: PostgreSQL', fontsize=7, ha='center')

# Save the diagram
plt.tight_layout()
output_path = '/Users/maverick/PycharmProjects/India-TS/Diagrams/ML_Market_Regime_Component_Diagram.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"Component diagram saved to: {output_path}")

# Also save as PDF for higher quality
pdf_path = '/Users/maverick/PycharmProjects/India-TS/Diagrams/ML_Market_Regime_Component_Diagram.pdf'
plt.savefig(pdf_path, format='pdf', bbox_inches='tight', facecolor='white')
print(f"PDF version saved to: {pdf_path}")

plt.show()