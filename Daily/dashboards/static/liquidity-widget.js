/**
 * Liquidity Widget Module
 * Shared module for displaying liquidity information across all dashboards
 */

class LiquidityWidget {
    constructor() {
        this.cache = {};
        this.apiUrl = 'http://localhost:5555';
    }

    /**
     * Fetch liquidity data for a ticker
     */
    async fetchLiquidityData(ticker) {
        try {
            if (this.cache[ticker]) {
                return this.cache[ticker];
            }

            const response = await fetch(`${this.apiUrl}/liquidity/${ticker}`);
            if (response.ok) {
                const data = await response.json();
                if (data.data) {
                    this.cache[ticker] = data.data;
                    return data.data;
                }
            }
        } catch (error) {
            console.error(`Failed to fetch liquidity for ${ticker}:`, error);
        }
        return null;
    }

    /**
     * Get liquidity grade color
     */
    getLiquidityColor(grade) {
        const colors = {
            'A+': '#10b981',
            'A': '#10b981',
            'B': '#3b82f6',
            'C': '#f59e0b',
            'D': '#ef4444',
            'F': '#6b7280'
        };
        return colors[grade] || '#6b7280';
    }

    /**
     * Get liquidity rank text
     */
    getLiquidityRank(grade) {
        const ranks = {
            'A+': 'Excellent',
            'A': 'Very High',
            'B': 'High',
            'C': 'Medium',
            'D': 'Low',
            'F': 'Very Low'
        };
        return ranks[grade] || 'Unknown';
    }

    /**
     * Get trade size category
     */
    getTradeSize(turnoverCr) {
        if (turnoverCr >= 100) return 'Large Cap';
        if (turnoverCr >= 50) return 'Mid-Large';
        if (turnoverCr >= 20) return 'Mid Cap';
        if (turnoverCr >= 10) return 'Small-Mid';
        if (turnoverCr >= 5) return 'Small Cap';
        return 'Micro Cap';
    }

    /**
     * Create a simple liquidity badge HTML
     */
    createSimpleBadge(data) {
        if (!data) return '';
        
        const grade = data.liquidity_grade || 'F';
        const score = data.liquidity_score || 0;
        const color = this.getLiquidityColor(grade);
        
        return `
            <span style="
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 0.85rem;
                font-weight: 600;
                background: ${color}20;
                color: ${color};
                border: 1px solid ${color}40;
            ">
                Liq: ${grade} (${score})
            </span>
        `;
    }

    /**
     * Create a detailed liquidity card HTML
     */
    createDetailedCard(data) {
        if (!data) return '';
        
        const grade = data.liquidity_grade || 'F';
        const score = data.liquidity_score || 0;
        const turnover = data.avg_daily_turnover_cr || 0;
        const color = this.getLiquidityColor(grade);
        const rank = this.getLiquidityRank(grade);
        const tradeSize = this.getTradeSize(turnover);
        
        return `
            <div style="
                background: #1a1a1a;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 12px;
                margin-top: 8px;
            ">
                <div style="
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 8px;
                ">
                    <span style="
                        font-size: 0.85rem;
                        color: #888;
                        text-transform: uppercase;
                        font-weight: 600;
                    ">Liquidity Analysis</span>
                    <span style="
                        display: inline-flex;
                        align-items: center;
                        gap: 4px;
                        padding: 2px 8px;
                        border-radius: 4px;
                        font-size: 0.9rem;
                        font-weight: 600;
                        background: ${color}20;
                        color: ${color};
                        border: 1px solid ${color}40;
                    ">
                        Grade ${grade}
                    </span>
                </div>
                
                <div style="
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 12px;
                    margin-top: 8px;
                ">
                    <div>
                        <div style="font-size: 0.7rem; color: #666;">Score</div>
                        <div style="font-size: 1rem; font-weight: 600; color: ${color};">
                            ${score}/100
                        </div>
                    </div>
                    <div>
                        <div style="font-size: 0.7rem; color: #666;">Turnover</div>
                        <div style="font-size: 1rem; font-weight: 600; color: #fff;">
                            ₹${turnover.toFixed(1)}Cr
                        </div>
                    </div>
                    <div>
                        <div style="font-size: 0.7rem; color: #666;">Rank</div>
                        <div style="font-size: 1rem; font-weight: 600; color: #fff;">
                            ${rank}
                        </div>
                    </div>
                </div>
                
                <div style="
                    margin-top: 8px;
                    padding-top: 8px;
                    border-top: 1px solid #333;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                ">
                    <span style="font-size: 0.75rem; color: #888;">Trade Size</span>
                    <span style="font-size: 0.85rem; color: #fff; font-weight: 500;">
                        ${tradeSize}
                    </span>
                </div>
            </div>
        `;
    }

    /**
     * Create inline liquidity info for tables
     */
    createInlineInfo(data) {
        if (!data) return 'N/A';
        
        const grade = data.liquidity_grade || 'F';
        const score = data.liquidity_score || 0;
        const turnover = data.avg_daily_turnover_cr || 0;
        const color = this.getLiquidityColor(grade);
        
        return `
            <span style="color: ${color}; font-weight: 600;">
                ${grade} (${score}) • ₹${turnover.toFixed(1)}Cr
            </span>
        `;
    }

    /**
     * Batch fetch liquidity data
     */
    async fetchBatch(tickers) {
        try {
            const response = await fetch(`${this.apiUrl}/liquidity/batch`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ tickers })
            });
            
            if (response.ok) {
                const data = await response.json();
                // Update cache with results
                if (data.results) {
                    Object.entries(data.results).forEach(([ticker, result]) => {
                        if (result.data) {
                            this.cache[ticker] = result.data;
                        }
                    });
                }
                return data.results;
            }
        } catch (error) {
            console.error('Failed to fetch batch liquidity:', error);
        }
        return {};
    }
}

// Create global instance
window.liquidityWidget = new LiquidityWidget();