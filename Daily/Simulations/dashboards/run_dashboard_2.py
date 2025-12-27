#!/usr/bin/env python3
"""Run Dashboard 2: Long + KC Middle SL"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboards.simulation_dashboard import run_dashboard

if __name__ == '__main__':
    run_dashboard('sim_2', 4002)
