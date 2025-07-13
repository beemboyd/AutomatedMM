#!/usr/bin/env python
import os
import sys
import shutil
import glob
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define the Daily directory
DAILY_DIR = os.path.dirname(os.path.abspath(__file__))

# Define subdirectories
SUBDIRS = {
    "scripts": "Python scripts",
    "scanner_files": "Scanner output files",
    "reports": "Analysis reports",
    "results": "Trading results",
    "data": "Input data files",
    "logs": "Log files",
    "Detailed_Analysis": "Detailed stock analysis reports"
}

def create_directory_structure():
    """Create the directory structure"""
    for subdir, description in SUBDIRS.items():
        dir_path = os.path.join(DAILY_DIR, subdir)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            logger.info(f"Created directory: {subdir} - {description}")
        else:
            logger.info(f"Directory already exists: {subdir}")

def move_files():
    """Move files to appropriate directories"""
    # Move Python scripts
    for script in glob.glob(os.path.join(DAILY_DIR, "*.py")):
        # Don't move the current script
        if os.path.basename(script) == "reorganize.py":
            continue
        
        dest = os.path.join(DAILY_DIR, "scripts", os.path.basename(script))
        shutil.move(script, dest)
        logger.info(f"Moved {os.path.basename(script)} to scripts/")
    
    # Move scanner files
    for scanner_file in glob.glob(os.path.join(DAILY_DIR, "Custom_Scanner_*.xlsx")):
        dest = os.path.join(DAILY_DIR, "scanner_files", os.path.basename(scanner_file))
        shutil.move(scanner_file, dest)
        logger.info(f"Moved {os.path.basename(scanner_file)} to scanner_files/")
    
    # Move result files
    result_patterns = [
        "Daily_SMA20_*.xlsx",
        "Keltner_Breakout_*.xlsx"
    ]
    for pattern in result_patterns:
        for result_file in glob.glob(os.path.join(DAILY_DIR, pattern)):
            dest = os.path.join(DAILY_DIR, "results", os.path.basename(result_file))
            shutil.move(result_file, dest)
            logger.info(f"Moved {os.path.basename(result_file)} to results/")
    
    # Move data files
    data_files = [
        "Ticker.xlsx",
        "instruments_backup.csv",
        "debug_output.csv"
    ]
    for data_file in data_files:
        src = os.path.join(DAILY_DIR, data_file)
        if os.path.exists(src):
            dest = os.path.join(DAILY_DIR, "data", data_file)
            shutil.move(src, dest)
            logger.info(f"Moved {data_file} to data/")
    
    # Move detailed analysis report files (if any)
    for report_file in glob.glob(os.path.join(DAILY_DIR, "Detailed_Analysis_*.html")):
        dest = os.path.join(DAILY_DIR, "Detailed_Analysis", os.path.basename(report_file))
        shutil.move(report_file, dest)
        logger.info(f"Moved {os.path.basename(report_file)} to Detailed_Analysis/")

    # Move other report files (if any)
    for report_file in glob.glob(os.path.join(DAILY_DIR, "*_Report_*.html")):
        dest = os.path.join(DAILY_DIR, "reports", os.path.basename(report_file))
        shutil.move(report_file, dest)
        logger.info(f"Moved {os.path.basename(report_file)} to reports/")

def create_init_files():
    """Create __init__.py files in each directory"""
    for subdir in SUBDIRS.keys():
        init_file = os.path.join(DAILY_DIR, subdir, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write(f"# {SUBDIRS[subdir]}\n")
            logger.info(f"Created __init__.py in {subdir}/")

def update_pattern_daily():
    """Update the Pattern_Daily.py script to work with the new directory structure"""
    pattern_daily_path = os.path.join(DAILY_DIR, "scripts", "Pattern_Daily.py")

    if not os.path.exists(pattern_daily_path):
        logger.warning("Pattern_Daily.py not found in scripts/ directory")
        return

    with open(pattern_daily_path, 'r') as f:
        content = f.read()

    # Update path to scanner files
    content = content.replace(
        'script_dir = os.path.dirname(os.path.abspath(__file__))',
        'daily_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n        scanner_dir = os.path.join(daily_dir, "scanner_files")'
    )
    content = content.replace(
        'scanner_files = glob.glob(os.path.join(script_dir, "Custom_Scanner_*.xlsx"))',
        'scanner_files = glob.glob(os.path.join(scanner_dir, "Custom_Scanner_*.xlsx"))'
    )

    # Update error message
    content = content.replace(
        'No scanner files found in the Daily directory',
        'No scanner files found in the scanner_files directory'
    )

    # Update report file path
    content = content.replace(
        'report_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"Detailed_Analysis_{today}.html")',
        'report_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Detailed_Analysis")\n        os.makedirs(report_dir, exist_ok=True)\n        report_file = os.path.join(report_dir, f"Detailed_Analysis_{today}.html")'
    )

    with open(pattern_daily_path, 'w') as f:
        f.write(content)

    logger.info("Updated Pattern_Daily.py to work with the new directory structure")

def update_daily_py():
    """Update the Daily.py script to work with the new directory structure"""
    daily_py_path = os.path.join(DAILY_DIR, "scripts", "Daily.py")
    
    if not os.path.exists(daily_py_path):
        logger.warning("Daily.py not found in scripts/ directory")
        return
    
    with open(daily_py_path, 'r') as f:
        content = f.read()
    
    # Update paths
    content = content.replace(
        'input_file_path = os.path.join(SCRIPT_DIR, "Ticker.xlsx")',
        'input_file_path = os.path.join(os.path.dirname(SCRIPT_DIR), "data", "Ticker.xlsx")'
    )
    content = content.replace(
        'output_file_path = os.path.join(SCRIPT_DIR, f\'Custom_Scanner_{formatted_date}_{formatted_time}.xlsx\')',
        'output_file_path = os.path.join(os.path.dirname(SCRIPT_DIR), "scanner_files", f\'Custom_Scanner_{formatted_date}_{formatted_time}.xlsx\')'
    )
    content = content.replace(
        'backup_file = os.path.join(SCRIPT_DIR, "instruments_backup.csv")',
        'backup_file = os.path.join(os.path.dirname(SCRIPT_DIR), "data", "instruments_backup.csv")'
    )
    
    with open(daily_py_path, 'w') as f:
        f.write(content)
    
    logger.info("Updated Daily.py to work with the new directory structure")

def update_other_scripts():
    """Update any other scripts that might need updating"""
    # Update Daily-SMA20.py
    sma20_path = os.path.join(DAILY_DIR, "scripts", "Daily-SMA20.py")
    
    if os.path.exists(sma20_path):
        with open(sma20_path, 'r') as f:
            content = f.read()
        
        # Update output path
        content = content.replace(
            'output_path = os.path.join(script_dir, f"Daily_SMA20_{today.strftime(\'%d_%m_%Y_%H_%M\')}.xlsx")',
            'output_path = os.path.join(os.path.dirname(script_dir), "results", f"Daily_SMA20_{today.strftime(\'%d_%m_%Y_%H_%M\')}.xlsx")'
        )
        
        with open(sma20_path, 'w') as f:
            f.write(content)
        
        logger.info("Updated Daily-SMA20.py")

def main():
    """Main function to reorganize the Daily directory"""
    logger.info("Starting reorganization of Daily directory")
    
    create_directory_structure()
    move_files()
    create_init_files()
    
    # Update scripts to work with the new directory structure
    update_pattern_daily()
    update_daily_py()
    update_other_scripts()
    
    # Delete this script
    os.remove(os.path.abspath(__file__))
    
    logger.info("Reorganization complete!")
    logger.info("The Daily directory has been organized into subdirectories.")
    logger.info("All scripts have been updated to work with the new structure.")

if __name__ == "__main__":
    main()