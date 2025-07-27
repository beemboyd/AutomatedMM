#!/usr/bin/env python3
"""
SMA Breadth Dashboard Integration
Creates a proper line chart visualization for historical SMA breadth data
"""

import json
import os
from datetime import datetime

def generate_sma_breadth_html():
    """Generate HTML section for SMA Breadth visualization"""
    
    html = """
        <!-- SMA Breadth Historical Analysis Section -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">📊 SMA Breadth Historical Analysis <small class="text-success">[176 stocks tracked]</small></h5>
                        
                        <!-- Combined Line Chart -->
                        <div class="chart-container" style="height: 400px; position: relative;">
                            <canvas id="sma-breadth-combined-chart"></canvas>
                        </div>
                        
                        <!-- Current Stats Row -->
                        <div class="row mt-3">
                            <div class="col-12">
                                <div class="alert alert-info mb-0">
                                    <div class="row text-center">
                                        <div class="col-md-2">
                                            <strong>Current SMA20:</strong><br>
                                            <span id="current-sma20-breadth" class="h5">-</span>%
                                        </div>
                                        <div class="col-md-2">
                                            <strong>Current SMA50:</strong><br>
                                            <span id="current-sma50-breadth" class="h5">-</span>%
                                        </div>
                                        <div class="col-md-2">
                                            <strong>Market Regime:</strong><br>
                                            <span id="current-market-regime" class="h5">-</span>
                                        </div>
                                        <div class="col-md-2">
                                            <strong>Market Score:</strong><br>
                                            <span id="current-market-score" class="h5">-</span>
                                        </div>
                                        <div class="col-md-2">
                                            <strong>5-Day Trend:</strong><br>
                                            <span id="sma-5day-trend" class="h5">-</span>
                                        </div>
                                        <div class="col-md-2">
                                            <strong>20-Day Trend:</strong><br>
                                            <span id="sma-20day-trend" class="h5">-</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Breadth Levels Analysis -->
                        <div class="row mt-3">
                            <div class="col-md-6">
                                <div class="card bg-light">
                                    <div class="card-body">
                                        <h6 class="card-subtitle mb-2 text-muted">Breadth Zones</h6>
                                        <small>
                                            <div><span class="badge bg-success">Strong Bullish</span> SMA20 & SMA50 > 70%</div>
                                            <div><span class="badge bg-primary">Bullish</span> SMA20 & SMA50 > 60%</div>
                                            <div><span class="badge bg-secondary">Neutral</span> Between 30-60%</div>
                                            <div><span class="badge bg-warning">Bearish</span> SMA20 & SMA50 < 40%</div>
                                            <div><span class="badge bg-danger">Strong Bearish</span> SMA20 & SMA50 < 30%</div>
                                        </small>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card bg-light">
                                    <div class="card-body">
                                        <h6 class="card-subtitle mb-2 text-muted">Key Statistics</h6>
                                        <small>
                                            <div>Data Points: <span id="sma-data-points">-</span> days</div>
                                            <div>Date Range: <span id="sma-date-range">-</span></div>
                                            <div>Stocks Tracked: <span id="sma-stocks-tracked">-</span></div>
                                            <div>Last Update: <span id="sma-last-update">-</span></div>
                                        </small>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    """
    
    return html


def generate_sma_breadth_javascript():
    """Generate JavaScript for SMA Breadth chart initialization and updates"""
    
    js = """
        // SMA Breadth Chart Variables
        let smaBreadthCombinedChart = null;
        
        // Initialize SMA Breadth Combined Chart
        function initializeSMABreadthChart() {
            const ctx = document.getElementById('sma-breadth-combined-chart');
            if (!ctx) {
                console.error('SMA Breadth canvas element not found');
                return;
            }
            
            smaBreadthCombinedChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'SMA20 Breadth %',
                            data: [],
                            borderColor: 'rgb(54, 162, 235)',
                            backgroundColor: 'rgba(54, 162, 235, 0.1)',
                            borderWidth: 2,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5
                        },
                        {
                            label: 'SMA50 Breadth %',
                            data: [],
                            borderColor: 'rgb(255, 99, 132)',
                            backgroundColor: 'rgba(255, 99, 132, 0.1)',
                            borderWidth: 2,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5
                        },
                        {
                            label: 'Market Score',
                            data: [],
                            borderColor: 'rgb(153, 102, 255)',
                            backgroundColor: 'rgba(153, 102, 255, 0.1)',
                            borderWidth: 2,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 5,
                            yAxisID: 'y1',
                            hidden: true
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: 'Market Breadth Historical Trend (SMA20 vs SMA50)'
                        },
                        legend: {
                            display: true,
                            position: 'top'
                        },
                        tooltip: {
                            callbacks: {
                                afterLabel: function(context) {
                                    if (context.datasetIndex < 2) {
                                        return context.parsed.y.toFixed(1) + '%';
                                    }
                                    return context.parsed.y.toFixed(3);
                                }
                            }
                        },
                        annotation: {
                            annotations: {
                                bullishZone: {
                                    type: 'box',
                                    yMin: 70,
                                    yMax: 100,
                                    backgroundColor: 'rgba(0, 255, 0, 0.05)',
                                    borderColor: 'transparent'
                                },
                                bearishZone: {
                                    type: 'box',
                                    yMin: 0,
                                    yMax: 30,
                                    backgroundColor: 'rgba(255, 0, 0, 0.05)',
                                    borderColor: 'transparent'
                                },
                                midLine: {
                                    type: 'line',
                                    yMin: 50,
                                    yMax: 50,
                                    borderColor: 'rgba(128, 128, 128, 0.5)',
                                    borderWidth: 1,
                                    borderDash: [5, 5]
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Date'
                            },
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45,
                                autoSkip: true,
                                maxTicksLimit: 20
                            }
                        },
                        y: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Breadth %'
                            },
                            min: 0,
                            max: 100,
                            ticks: {
                                callback: function(value) {
                                    return value + '%';
                                }
                            }
                        },
                        y1: {
                            display: false,
                            position: 'right',
                            title: {
                                display: true,
                                text: 'Market Score'
                            },
                            min: 0,
                            max: 1,
                            grid: {
                                drawOnChartArea: false
                            }
                        }
                    }
                }
            });
        }
        
        // Update SMA Breadth Chart
        function updateSMABreadthChart(data) {
            if (!smaBreadthCombinedChart) {
                console.error('SMA Breadth chart not initialized');
                return;
            }
            
            try {
                // Update chart data
                smaBreadthCombinedChart.data.labels = data.labels;
                smaBreadthCombinedChart.data.datasets[0].data = data.sma20_values;
                smaBreadthCombinedChart.data.datasets[1].data = data.sma50_values;
                
                // Add market score if available
                if (data.market_scores) {
                    smaBreadthCombinedChart.data.datasets[2].data = data.market_scores;
                }
                
                smaBreadthCombinedChart.update();
                
                // Update current stats
                document.getElementById('current-sma20-breadth').textContent = data.current_sma20.toFixed(1);
                document.getElementById('current-sma50-breadth').textContent = data.current_sma50.toFixed(1);
                document.getElementById('current-market-regime').textContent = data.market_regime;
                document.getElementById('current-market-score').textContent = data.market_score ? data.market_score.toFixed(3) : '-';
                
                // Update trends with arrows
                const sma20Trend = data.sma20_5d_change > 0 ? '↑' : '↓';
                const sma50Trend = data.sma50_5d_change > 0 ? '↑' : '↓';
                const trend5d = `SMA20: ${sma20Trend} ${Math.abs(data.sma20_5d_change).toFixed(1)}%<br>SMA50: ${sma50Trend} ${Math.abs(data.sma50_5d_change).toFixed(1)}%`;
                
                const sma20Trend20d = data.sma20_20d_change > 0 ? '↑' : '↓';
                const sma50Trend20d = data.sma50_20d_change > 0 ? '↑' : '↓';
                const trend20d = `SMA20: ${sma20Trend20d} ${Math.abs(data.sma20_20d_change).toFixed(1)}%<br>SMA50: ${sma50Trend20d} ${Math.abs(data.sma50_20d_change).toFixed(1)}%`;
                
                document.getElementById('sma-5day-trend').innerHTML = trend5d;
                document.getElementById('sma-20day-trend').innerHTML = trend20d;
                
                // Update statistics
                document.getElementById('sma-data-points').textContent = data.data_points;
                document.getElementById('sma-date-range').textContent = data.date_range;
                document.getElementById('sma-stocks-tracked').textContent = data.total_stocks;
                document.getElementById('sma-last-update').textContent = new Date().toLocaleTimeString();
                
                // Color code regime
                const regimeElement = document.getElementById('current-market-regime');
                regimeElement.className = 'h5';
                if (data.market_regime.includes('Strong Uptrend')) {
                    regimeElement.classList.add('text-success');
                } else if (data.market_regime.includes('Uptrend')) {
                    regimeElement.classList.add('text-primary');
                } else if (data.market_regime.includes('Strong Downtrend')) {
                    regimeElement.classList.add('text-danger');
                } else if (data.market_regime.includes('Downtrend')) {
                    regimeElement.classList.add('text-warning');
                } else {
                    regimeElement.classList.add('text-secondary');
                }
                
            } catch (error) {
                console.error('Error updating SMA breadth chart:', error);
            }
        }
        
        // Fetch SMA Breadth Data
        function fetchSMABreadthData() {
            fetch('/api/sma-breadth-historical')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error('Error fetching SMA breadth data:', data.error);
                        return;
                    }
                    updateSMABreadthChart(data);
                })
                .catch(error => {
                    console.error('Error fetching SMA breadth data:', error);
                });
        }
    """
    
    return js


def generate_api_endpoint():
    """Generate the API endpoint code for Flask"""
    
    endpoint = '''
@app.route('/api/sma-breadth-historical')
def get_sma_breadth_historical():
    """Get historical SMA breadth data"""
    try:
        # Load historical data
        data_file = os.path.join(app.config['REGIME_DIR'], 'historical_breadth_data', 'sma_breadth_historical_latest.json')
        
        if not os.path.exists(data_file):
            return jsonify({'error': 'Historical data not found'})
        
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        if not data:
            return jsonify({'error': 'No data available'})
        
        # Calculate trend metrics
        current = data[-1]
        five_days_ago = data[-6] if len(data) >= 6 else data[0]
        twenty_days_ago = data[-21] if len(data) >= 21 else data[0]
        
        sma20_5d_change = current['sma_breadth']['sma20_percent'] - five_days_ago['sma_breadth']['sma20_percent']
        sma50_5d_change = current['sma_breadth']['sma50_percent'] - five_days_ago['sma_breadth']['sma50_percent']
        sma20_20d_change = current['sma_breadth']['sma20_percent'] - twenty_days_ago['sma_breadth']['sma20_percent']
        sma50_20d_change = current['sma_breadth']['sma50_percent'] - twenty_days_ago['sma_breadth']['sma50_percent']
        
        # Prepare response
        response_data = {
            'labels': [d['date'] for d in data],
            'sma20_values': [d['sma_breadth']['sma20_percent'] for d in data],
            'sma50_values': [d['sma_breadth']['sma50_percent'] for d in data],
            'market_scores': [d['market_score'] for d in data],
            'data_points': len(data),
            'current_sma20': current['sma_breadth']['sma20_percent'],
            'current_sma50': current['sma_breadth']['sma50_percent'],
            'market_regime': current['market_regime'],
            'market_score': current['market_score'],
            'total_stocks': current['total_stocks'],
            'date_range': f"{data[0]['date']} to {data[-1]['date']}",
            'sma20_5d_change': sma20_5d_change,
            'sma50_5d_change': sma50_5d_change,
            'sma20_20d_change': sma20_20d_change,
            'sma50_20d_change': sma50_20d_change
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"Error in get_sma_breadth_historical: {e}")
        return jsonify({'error': str(e)})
'''
    
    return endpoint


def main():
    """Main function to display integration instructions"""
    
    print("=== SMA Breadth Dashboard Integration ===\n")
    
    print("1. HTML Section to add (replace the commented out SMA breadth section):")
    print("-" * 60)
    print(generate_sma_breadth_html())
    print("-" * 60)
    
    print("\n2. JavaScript to add to the script section:")
    print("-" * 60)
    print(generate_sma_breadth_javascript())
    print("-" * 60)
    
    print("\n3. Add this to the initialization code:")
    print("-" * 60)
    print("""
        // In the DOMContentLoaded event or initialization function:
        initializeSMABreadthChart();
        fetchSMABreadthData();
        
        // In the update interval (with other API calls):
        setInterval(fetchSMABreadthData, 60000); // Update every minute
    """)
    print("-" * 60)
    
    print("\n4. Flask API endpoint to add:")
    print("-" * 60)
    print(generate_api_endpoint())
    print("-" * 60)
    
    print("\n5. Required imports at the top of dashboard_enhanced.py:")
    print("-" * 60)
    print("""
import json
import os
from datetime import datetime
    """)
    print("-" * 60)
    
    print("\n✓ Integration code generated successfully!")
    print("\nNote: This will create a combined line chart showing both SMA20 and SMA50 breadth")
    print("with proper trend analysis and market regime indicators.")


if __name__ == "__main__":
    main()