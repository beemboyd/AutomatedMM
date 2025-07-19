"""
Utility functions for MCP servers
"""

import pandas as pd
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

def read_transaction_excel(filepath: Path) -> pd.DataFrame:
    """
    Read transaction Excel file with proper handling
    """
    try:
        # Try reading with different engines
        try:
            df = pd.read_excel(filepath, engine='openpyxl')
        except:
            df = pd.read_excel(filepath)
        
        # If no columns, try reading specific sheet
        if df.empty or len(df.columns) == 0:
            # Try reading the first sheet explicitly
            excel_file = pd.ExcelFile(filepath)
            if excel_file.sheet_names:
                df = pd.read_excel(filepath, sheet_name=excel_file.sheet_names[0])
        
        return df
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return pd.DataFrame()

def parse_order_filename(filename: str) -> Optional[datetime]:
    """
    Parse date from order filename
    Format: orders_UserName_YYYYMMDD_HHMMSS.json
    """
    try:
        parts = filename.split('_')
        if len(parts) >= 3:
            date_str = parts[2]
            return datetime.strptime(date_str, '%Y%m%d')
    except:
        pass
    return None

def calculate_portfolio_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate standard portfolio metrics from transaction data
    """
    metrics = {
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "total_pnl": 0.0,
        "avg_pnl": 0.0,
        "win_rate": 0.0,
        "max_gain": 0.0,
        "max_loss": 0.0,
        "sharpe_ratio": 0.0
    }
    
    if df.empty:
        return metrics
    
    # Look for PnL columns (might be named differently)
    pnl_columns = [col for col in df.columns if 'pnl' in col.lower() or 'p&l' in col.lower() or 'profit' in col.lower()]
    
    if pnl_columns:
        pnl_col = pnl_columns[0]
        df['PnL'] = pd.to_numeric(df[pnl_col], errors='coerce')
        
        # Remove NaN values
        pnl_series = df['PnL'].dropna()
        
        if len(pnl_series) > 0:
            metrics["total_trades"] = len(pnl_series)
            metrics["winning_trades"] = len(pnl_series[pnl_series > 0])
            metrics["losing_trades"] = len(pnl_series[pnl_series < 0])
            metrics["total_pnl"] = float(pnl_series.sum())
            metrics["avg_pnl"] = float(pnl_series.mean())
            metrics["win_rate"] = (metrics["winning_trades"] / metrics["total_trades"] * 100) if metrics["total_trades"] > 0 else 0
            metrics["max_gain"] = float(pnl_series.max()) if len(pnl_series) > 0 else 0
            metrics["max_loss"] = float(pnl_series.min()) if len(pnl_series) > 0 else 0
            
            # Calculate Sharpe ratio
            if len(pnl_series) > 1 and pnl_series.std() > 0:
                sharpe = (pnl_series.mean() / pnl_series.std() * (252 ** 0.5))
                metrics["sharpe_ratio"] = float(sharpe)
    
    return metrics

def aggregate_order_data(order_files: List[Path], days: int = 7) -> List[Dict[str, Any]]:
    """
    Aggregate order data from multiple files
    """
    cutoff_date = datetime.now() - pd.Timedelta(days=days)
    aggregated_orders = []
    
    for order_file in order_files:
        file_date = parse_order_filename(order_file.name)
        if file_date and file_date >= cutoff_date:
            try:
                with open(order_file, 'r') as f:
                    data = json.load(f)
                    
                if isinstance(data, list):
                    for order in data:
                        order['file_date'] = file_date.isoformat()
                        aggregated_orders.append(order)
                else:
                    data['file_date'] = file_date.isoformat()
                    aggregated_orders.append(data)
            except Exception as e:
                print(f"Error reading {order_file}: {e}")
    
    return aggregated_orders

def format_currency(value: float) -> str:
    """
    Format currency values for display
    """
    if abs(value) >= 10000000:  # Crore
        return f"₹{value/10000000:.2f}Cr"
    elif abs(value) >= 100000:  # Lakh
        return f"₹{value/100000:.2f}L"
    elif abs(value) >= 1000:  # Thousand
        return f"₹{value/1000:.2f}K"
    else:
        return f"₹{value:.2f}"