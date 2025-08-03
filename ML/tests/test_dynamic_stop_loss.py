import os
import sys
import logging
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ML.models.dynamic_stop_loss import DynamicStopLossModel, PositionType
from ML.utils.atr_calculator import ATRCalculator
from ML.utils.market_regime import MarketRegimeDetector, MarketRegimeType
from data_handler import get_data_handler
from config import get_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DynamicStopLossEvaluator:
    """
    Evaluates the performance of dynamic stop loss strategies.
    """
    
    def __init__(self):
        """Initialize the evaluator"""
        self.config = get_config()
        self.data_handler = get_data_handler()
        self.stop_loss_model = DynamicStopLossModel()
        self.atr_calculator = ATRCalculator(period=14)
        self.regime_detector = MarketRegimeDetector()
        
        # Default testing parameters
        self.lookback_days = 30
        self.eval_tickers = []
        
        # Load tickers from test file if available
        test_ticker_file = self.config.get('ML', 'test_ticker_file', fallback='')
        if test_ticker_file and os.path.exists(test_ticker_file):
            try:
                df = pd.read_excel(test_ticker_file)
                if 'Symbol' in df.columns:
                    self.eval_tickers = df['Symbol'].tolist()
                    logger.info(f"Loaded {len(self.eval_tickers)} test tickers from {test_ticker_file}")
            except Exception as e:
                logger.error(f"Error loading test tickers: {str(e)}")
        
        # If no tickers loaded, use a default set
        if not self.eval_tickers:
            default_tickers = ["RELIANCE", "TCS", "ICICIBANK", "HDFCBANK", "SBIN"]
            self.eval_tickers = default_tickers
            logger.info(f"Using default test tickers: {default_tickers}")
        
        # Output directory for results
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
        os.makedirs(self.output_dir, exist_ok=True)
    
    def get_historical_data(self, ticker, timeframe="day", days=30):
        """
        Get historical data for a ticker.
        
        Args:
            ticker (str): Ticker symbol
            timeframe (str): Timeframe/interval for data
            days (int): Number of days to look back
            
        Returns:
            pd.DataFrame: Historical OHLC data
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Use data handler to fetch historical data
            data = self.data_handler.get_historical_data(
                ticker, 
                timeframe=timeframe, 
                start_date=start_date,
                end_date=end_date
            )
            
            # Fall back to reading data files if data handler fails
            if data is None or len(data) < 10:
                logger.warning(f"Insufficient data from data handler for {ticker}, trying data files")
                file_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    'BT', 'data', f'{ticker}_day.csv'
                )
                
                if os.path.exists(file_path):
                    data = pd.read_csv(file_path)
                    data['Date'] = pd.to_datetime(data['Date'])
                    data = data.set_index('Date')
                    data = data.loc[start_date:end_date]
                    logger.info(f"Loaded {len(data)} rows from data file for {ticker}")
                else:
                    logger.error(f"No data file found for {ticker}")
                    return None
            
            # Ensure we have enough data
            if data is None or len(data) < 10:
                logger.warning(f"Still insufficient data for {ticker}: Got {len(data) if data is not None else 0} points")
                return None
            
            # Ensure data has required columns
            required_columns = ['Open', 'High', 'Low', 'Close']
            if not all(col in data.columns for col in required_columns):
                logger.error(f"Missing required columns in data for {ticker}")
                return None
            
            return data
        
        except Exception as e:
            logger.error(f"Error fetching historical data for {ticker}: {str(e)}")
            return None
    
    def evaluate_stop_loss_strategy(self, ticker, position_type="LONG", timeframe="day", days=30):
        """
        Evaluate the effectiveness of different stop loss strategies for a ticker.
        
        Args:
            ticker (str): Ticker symbol to evaluate
            position_type (str): Type of position ('LONG' or 'SHORT')
            timeframe (str): Timeframe/interval for data
            days (int): Number of days to look back
            
        Returns:
            pd.DataFrame: DataFrame with evaluation results
        """
        try:
            # Get historical data
            data = self.get_historical_data(ticker, timeframe, days)
            if data is None:
                logger.warning(f"No historical data available for {ticker}")
                return None
            
            # Calculate ATR
            atr = self.atr_calculator.calculate_atr(data)
            data['ATR'] = atr
            
            # Detect market regime
            regime, regime_metrics = self.regime_detector.detect_consolidated_regime(data)
            data['Regime'] = regime
            
            # Create evaluation DataFrame
            eval_df = pd.DataFrame(index=data.index)
            eval_df['Close'] = data['Close']
            
            # Calculate stop losses using different methods
            # 1. Fixed ATR multiplier (1.5)
            if position_type.upper() == "LONG":
                eval_df['Fixed_SL'] = data['Close'] - (1.5 * data['ATR'])
            else:
                eval_df['Fixed_SL'] = data['Close'] + (1.5 * data['ATR'])
            
            # 2. Dynamic ATR based on market regime (rule-based)
            stop_losses = []
            for i in range(len(data)):
                row = data.iloc[i:i+1]
                price = row['Close'].iloc[0]
                if i >= 1:  # Use previous close to simulate real conditions
                    price = data['Close'].iloc[i-1]
                
                stop_loss = self.stop_loss_model.calculate_rule_based_stop_loss(
                    data.iloc[:i+1], price, position_type)
                stop_losses.append(stop_loss)
            
            eval_df['Dynamic_SL'] = stop_losses
            
            # 3. ML-based if model is trained (placeholder, would need training first)
            # This would be replaced with actual model predictions if trained
            
            # Prepare simulation data
            eval_df['Next_Low'] = data['Low'].shift(-1)
            eval_df['Next_High'] = data['High'].shift(-1)
            
            # Simulate stop loss hits
            if position_type.upper() == "LONG":
                eval_df['Fixed_Hit'] = eval_df['Next_Low'] <= eval_df['Fixed_SL']
                eval_df['Dynamic_Hit'] = eval_df['Next_Low'] <= eval_df['Dynamic_SL']
            else:
                eval_df['Fixed_Hit'] = eval_df['Next_High'] >= eval_df['Fixed_SL']
                eval_df['Dynamic_Hit'] = eval_df['Next_High'] >= eval_df['Dynamic_SL']
            
            # Calculate metrics
            metrics = {}
            
            # Total hit rate (what % of positions would be stopped out)
            metrics['Fixed_Hit_Rate'] = eval_df['Fixed_Hit'].mean() * 100
            metrics['Dynamic_Hit_Rate'] = eval_df['Dynamic_Hit'].mean() * 100
            
            # Average stop distance (% from price to stop)
            if position_type.upper() == "LONG":
                eval_df['Fixed_Distance'] = (eval_df['Close'] - eval_df['Fixed_SL']) / eval_df['Close'] * 100
                eval_df['Dynamic_Distance'] = (eval_df['Close'] - eval_df['Dynamic_SL']) / eval_df['Close'] * 100
            else:
                eval_df['Fixed_Distance'] = (eval_df['Fixed_SL'] - eval_df['Close']) / eval_df['Close'] * 100
                eval_df['Dynamic_Distance'] = (eval_df['Dynamic_SL'] - eval_df['Close']) / eval_df['Close'] * 100
            
            metrics['Fixed_Avg_Distance'] = eval_df['Fixed_Distance'].mean()
            metrics['Dynamic_Avg_Distance'] = eval_df['Dynamic_Distance'].mean()
            
            # Premature stop rate (stops hit that would have recovered)
            # A "recoverable" stop is one where the price eventually goes back in your favor
            recoverable_stops = 0
            total_fixed_stops = 0
            
            for i in range(len(eval_df) - 5):  # Look ahead up to 5 days
                if eval_df['Fixed_Hit'].iloc[i]:
                    total_fixed_stops += 1
                    # For longs, check if any of the next 5 days close higher than entry
                    if position_type.upper() == "LONG":
                        future_closes = eval_df['Close'].iloc[i+1:i+6]
                        if any(future_closes > eval_df['Close'].iloc[i]):
                            recoverable_stops += 1
                    else:  # For shorts
                        future_closes = eval_df['Close'].iloc[i+1:i+6]
                        if any(future_closes < eval_df['Close'].iloc[i]):
                            recoverable_stops += 1
            
            if total_fixed_stops > 0:
                metrics['Fixed_Premature_Stop_Rate'] = (recoverable_stops / total_fixed_stops) * 100
            else:
                metrics['Fixed_Premature_Stop_Rate'] = 0.0
            
            # Repeat for dynamic stops
            recoverable_stops = 0
            total_dynamic_stops = 0
            
            for i in range(len(eval_df) - 5):
                if eval_df['Dynamic_Hit'].iloc[i]:
                    total_dynamic_stops += 1
                    if position_type.upper() == "LONG":
                        future_closes = eval_df['Close'].iloc[i+1:i+6]
                        if any(future_closes > eval_df['Close'].iloc[i]):
                            recoverable_stops += 1
                    else:
                        future_closes = eval_df['Close'].iloc[i+1:i+6]
                        if any(future_closes < eval_df['Close'].iloc[i]):
                            recoverable_stops += 1
            
            if total_dynamic_stops > 0:
                metrics['Dynamic_Premature_Stop_Rate'] = (recoverable_stops / total_dynamic_stops) * 100
            else:
                metrics['Dynamic_Premature_Stop_Rate'] = 0.0
            
            logger.info(f"Evaluation results for {ticker} ({position_type}):")
            for key, value in metrics.items():
                logger.info(f"  {key}: {value:.2f}")
            
            return eval_df, metrics
        
        except Exception as e:
            logger.error(f"Error evaluating stop loss strategy for {ticker}: {str(e)}")
            return None, {}
    
    def plot_stop_loss_evaluation(self, ticker, eval_df, metrics, position_type="LONG"):
        """
        Plot the stop loss evaluation results.
        
        Args:
            ticker (str): Ticker symbol
            eval_df (pd.DataFrame): Evaluation DataFrame
            metrics (dict): Evaluation metrics
            position_type (str): Type of position ('LONG' or 'SHORT')
            
        Returns:
            str: Path to saved plot file
        """
        try:
            plt.figure(figsize=(12, 8))
            
            # Plot price and stop losses
            plt.subplot(2, 1, 1)
            plt.plot(eval_df.index, eval_df['Close'], label='Close Price', color='black')
            plt.plot(eval_df.index, eval_df['Fixed_SL'], label='Fixed ATR Stop Loss', linestyle='--', color='red')
            plt.plot(eval_df.index, eval_df['Dynamic_SL'], label='Dynamic Stop Loss', linestyle='--', color='green')
            
            plt.title(f"{ticker} Stop Loss Evaluation ({position_type})")
            plt.ylabel('Price')
            plt.legend()
            plt.grid(True)
            
            # Plot stop loss distance percentage
            plt.subplot(2, 1, 2)
            plt.plot(eval_df.index, eval_df['Fixed_Distance'], label='Fixed ATR Distance %', color='red')
            plt.plot(eval_df.index, eval_df['Dynamic_Distance'], label='Dynamic Distance %', color='green')
            
            plt.title(f"Stop Loss Distance (% from price)")
            plt.ylabel('Percentage')
            plt.legend()
            plt.grid(True)
            
            # Add metrics as text box
            metrics_text = "\n".join([f"{k}: {v:.2f}" for k, v in metrics.items()])
            plt.figtext(0.02, 0.02, metrics_text, fontsize=10, bbox=dict(facecolor='white', alpha=0.8))
            
            # Save plot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            plot_filename = f"{ticker}_{position_type}_stop_loss_eval_{timestamp}.png"
            plot_path = os.path.join(self.output_dir, plot_filename)
            plt.tight_layout()
            plt.savefig(plot_path)
            plt.close()
            
            logger.info(f"Saved evaluation plot to {plot_path}")
            return plot_path
        
        except Exception as e:
            logger.error(f"Error plotting stop loss evaluation: {str(e)}")
            return None
    
    def run_batch_evaluation(self, tickers=None, position_type="LONG", timeframe="day", days=30, plot=True):
        """
        Run batch evaluation for multiple tickers.
        
        Args:
            tickers (list): List of ticker symbols (uses default if None)
            position_type (str): Type of position ('LONG' or 'SHORT')
            timeframe (str): Timeframe/interval for data
            days (int): Number of days to look back
            plot (bool): Whether to generate plots
            
        Returns:
            pd.DataFrame: Summary of evaluation results
        """
        if tickers is None:
            tickers = self.eval_tickers
        
        results = []
        
        for ticker in tickers:
            logger.info(f"Evaluating stop loss strategies for {ticker}")
            eval_df, metrics = self.evaluate_stop_loss_strategy(ticker, position_type, timeframe, days)
            
            if eval_df is not None and metrics:
                metrics['Ticker'] = ticker
                results.append(metrics)
                
                if plot:
                    self.plot_stop_loss_evaluation(ticker, eval_df, metrics, position_type)
        
        # Create summary DataFrame
        if results:
            summary_df = pd.DataFrame(results)
            summary_df = summary_df.set_index('Ticker')
            
            # Save summary to CSV
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"stop_loss_evaluation_summary_{timestamp}.csv"
            csv_path = os.path.join(self.output_dir, csv_filename)
            summary_df.to_csv(csv_path)
            
            logger.info(f"Saved evaluation summary to {csv_path}")
            
            # Print average metrics
            avg_metrics = summary_df.mean()
            logger.info("Average metrics across all tickers:")
            for metric, value in avg_metrics.items():
                logger.info(f"  {metric}: {value:.2f}")
            
            return summary_df
        else:
            logger.warning("No valid results obtained from evaluation")
            return None

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Dynamic Stop Loss Evaluator')
    
    parser.add_argument('--tickers', type=str, nargs='+', 
                        help='List of ticker symbols to evaluate')
    parser.add_argument('--position-type', type=str, choices=['LONG', 'SHORT'], default='LONG',
                        help='Position type (LONG or SHORT)')
    parser.add_argument('--timeframe', type=str, default='day',
                        help='Timeframe for data (day, hour, etc.)')
    parser.add_argument('--days', type=int, default=30,
                        help='Number of days to look back')
    parser.add_argument('--no-plot', action='store_true',
                        help='Disable plot generation')
    
    return parser.parse_args()

def main():
    """Main function to run the evaluator"""
    args = parse_arguments()
    
    evaluator = DynamicStopLossEvaluator()
    evaluator.run_batch_evaluation(
        tickers=args.tickers,
        position_type=args.position_type,
        timeframe=args.timeframe,
        days=args.days,
        plot=not args.no_plot
    )

if __name__ == "__main__":
    main()