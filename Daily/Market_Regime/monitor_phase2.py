#!/usr/bin/env python3
"""
Phase 2 Monitoring Script
Monitors the feedback collection and validation process
"""

import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from regime_validation_pipeline import RegimeValidationPipeline

def print_header(title):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def check_feedback_database():
    """Check if feedback database exists and has data"""
    db_path = '/Users/maverick/PycharmProjects/India-TS/data/regime_feedback.db'
    
    if not os.path.exists(db_path):
        print("✗ Feedback database not found")
        print(f"  Expected at: {db_path}")
        return False
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("✓ Feedback database exists")
    print(f"  Tables: {', '.join([t[0] for t in tables])}")
    
    # Check feedback count
    cursor.execute("SELECT COUNT(*) FROM regime_feedback")
    feedback_count = cursor.fetchone()[0]
    
    # Get recent feedback
    cursor.execute("""
        SELECT COUNT(*) FROM regime_feedback 
        WHERE feedback_timestamp > datetime('now', '-1 hour')
    """)
    recent_count = cursor.fetchone()[0]
    
    print(f"  Total feedback records: {feedback_count}")
    print(f"  Feedback in last hour: {recent_count}")
    
    conn.close()
    return True

def check_predictions_status():
    """Check recent predictions and their feedback status"""
    pred_db = '/Users/maverick/PycharmProjects/India-TS/data/regime_learning.db'
    feedback_db = '/Users/maverick/PycharmProjects/India-TS/data/regime_feedback.db'
    
    conn_pred = sqlite3.connect(pred_db)
    conn_fb = sqlite3.connect(feedback_db)
    
    # Get predictions from last 2 hours
    cutoff = (datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor_pred = conn_pred.cursor()
    cursor_pred.execute("""
        SELECT id, timestamp, regime, confidence 
        FROM predictions 
        WHERE timestamp > ? 
        ORDER BY timestamp DESC 
        LIMIT 10
    """, (cutoff,))
    
    recent_predictions = cursor_pred.fetchall()
    
    print(f"\nRecent Predictions (last 2 hours):")
    print("-" * 60)
    
    for pred_id, timestamp, regime, confidence in recent_predictions:
        # Check if has feedback
        cursor_fb = conn_fb.cursor()
        cursor_fb.execute(
            "SELECT actual_regime, price_change_pct FROM regime_feedback WHERE prediction_id = ?",
            (pred_id,)
        )
        feedback = cursor_fb.fetchone()
        
        if feedback:
            actual_regime, price_change = feedback
            match = "✓" if regime == actual_regime else "✗"
            print(f"  [{timestamp}] {regime:15s} → {actual_regime:15s} {match} ({price_change:+.2f}%)")
        else:
            # Check if enough time has passed for feedback
            pred_time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            if datetime.now() - pred_time > timedelta(minutes=45):
                print(f"  [{timestamp}] {regime:15s} → [PENDING FEEDBACK]")
            else:
                mins_remaining = 45 - int((datetime.now() - pred_time).total_seconds() / 60)
                print(f"  [{timestamp}] {regime:15s} → [WAIT {mins_remaining}m]")
    
    conn_pred.close()
    conn_fb.close()

def show_accuracy_metrics():
    """Show current accuracy metrics"""
    feedback_db = '/Users/maverick/PycharmProjects/India-TS/data/regime_feedback.db'
    
    if not os.path.exists(feedback_db):
        print("No feedback database found")
        return
        
    conn = sqlite3.connect(feedback_db)
    cursor = conn.cursor()
    
    # Overall accuracy
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN predicted_regime = actual_regime THEN 1 ELSE 0 END) as correct
        FROM regime_feedback
    """)
    
    result = cursor.fetchone()
    if result and result[0] > 0:
        total, correct = result
        accuracy = (correct / total) * 100
        print(f"\nOverall Accuracy: {accuracy:.2f}% ({correct}/{total})")
    
    # Today's accuracy
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN predicted_regime = actual_regime THEN 1 ELSE 0 END) as correct
        FROM regime_feedback
        WHERE DATE(feedback_timestamp) = ?
    """, (today,))
    
    result = cursor.fetchone()
    if result and result[0] > 0:
        total, correct = result
        accuracy = (correct / total) * 100
        print(f"Today's Accuracy: {accuracy:.2f}% ({correct}/{total})")
    
    # Per-regime accuracy
    cursor.execute("""
        SELECT 
            predicted_regime,
            COUNT(*) as total,
            SUM(CASE WHEN predicted_regime = actual_regime THEN 1 ELSE 0 END) as correct
        FROM regime_feedback
        GROUP BY predicted_regime
        ORDER BY total DESC
    """)
    
    results = cursor.fetchall()
    if results:
        print("\nPer-Regime Accuracy:")
        print("-" * 40)
        for regime, total, correct in results:
            acc = (correct / total * 100) if total > 0 else 0
            print(f"  {regime:20s}: {acc:5.1f}% ({correct}/{total})")
    
    conn.close()

def check_service_status():
    """Check if feedback collector service is running"""
    import subprocess
    
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'regime_feedback_collector.py'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            pid = result.stdout.strip()
            print(f"✓ Feedback Collector Service is running (PID: {pid})")
            
            # Check log file
            log_file = '/Users/maverick/PycharmProjects/India-TS/Daily/logs/regime_feedback_collector.log'
            if os.path.exists(log_file):
                # Get last few lines of log
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    recent_lines = lines[-5:] if len(lines) >= 5 else lines
                    
                print("\nRecent log entries:")
                for line in recent_lines:
                    print(f"  {line.strip()}")
        else:
            print("✗ Feedback Collector Service is NOT running")
            print("  To start: ./Market_Regime/start_feedback_collector.sh")
            
    except Exception as e:
        print(f"Error checking service status: {e}")

def main():
    """Main monitoring function"""
    print_header("PHASE 2 MONITORING - REGIME FEEDBACK SYSTEM")
    
    # Check feedback database
    print_header("Feedback Database Status")
    db_exists = check_feedback_database()
    
    if db_exists:
        # Check predictions and feedback
        print_header("Prediction Feedback Status")
        check_predictions_status()
        
        # Show accuracy metrics
        print_header("Accuracy Metrics")
        show_accuracy_metrics()
        
        # Run validation pipeline
        print_header("Validation Pipeline Status")
        pipeline = RegimeValidationPipeline()
        
        # Check coverage
        coverage = pipeline.validate_feedback_coverage(hours=24)
        if coverage:
            print(f"Feedback Coverage: {coverage['coverage']:.1%} ({coverage['total_feedback']}/{coverage['total_predictions']})")
            status = "✓" if coverage['meets_threshold'] else "✗"
            print(f"  {status} Threshold: {coverage['threshold']:.0%}")
        
        # Check distribution
        distribution = pipeline.validate_regime_distribution(hours=24)
        if distribution:
            print(f"\nRegime Balance: {'✓ Balanced' if distribution['balanced'] else '✗ Imbalanced'}")
            if distribution['missing_regimes']:
                print(f"  Missing: {', '.join(distribution['missing_regimes'])}")
            if distribution['underrepresented']:
                print(f"  Underrepresented: {', '.join(distribution['underrepresented'])}")
        
        # Check readiness
        ready, message = pipeline.check_readiness_for_retraining()
        print(f"\nRetraining Readiness: {'✓ READY' if ready else '✗ NOT READY'}")
        print(f"  {message}")
    
    # Check service status
    print_header("Service Status")
    check_service_status()
    
    print("\n" + "="*60)
    print(" Monitoring Complete")
    print("="*60)
    
    # Save monitoring report
    report = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'database_exists': db_exists,
        'service_running': False  # Will be updated
    }
    
    report_path = f'/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/monitoring_reports/phase2_monitor_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved: {report_path}")

if __name__ == "__main__":
    main()