#!/usr/bin/env python
"""
Wrapper script to run Daily_improved.py with the correct paths.
This script ensures that all paths are correctly set up before executing.
"""

import os
import sys
import subprocess
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def main():
    """Run the Daily_improved.py script with the correct environment setup"""
    try:
        # Get the directory containing this script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Ensure the data directory exists
        data_dir = os.path.join(current_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # Ensure the scanner_files directory exists
        scanner_dir = os.path.join(current_dir, 'scanner_files')
        os.makedirs(scanner_dir, exist_ok=True)
        
        # Path to the virtual environment python
        venv_python = os.path.join(os.path.dirname(os.path.dirname(current_dir)), '.venv', 'bin', 'python')
        
        # Path to the script
        script_path = os.path.join(current_dir, 'scripts', 'Daily_improved.py')
        
        # Check if paths exist
        if not os.path.exists(venv_python):
            logger.error(f"Python interpreter not found at {venv_python}")
            return 1
            
        if not os.path.exists(script_path):
            logger.error(f"Script not found at {script_path}")
            return 1
        
        # Run the script
        logger.info(f"Running {script_path} with {venv_python}")
        result = subprocess.run([venv_python, script_path], check=True)
        
        return result.returncode
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running Daily_improved.py: {e}")
        return e.returncode
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())