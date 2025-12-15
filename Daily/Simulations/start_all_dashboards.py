#!/usr/bin/env python3
"""
Start All Simulation Dashboards
Launches dashboards on ports 4001-4004 for all 4 simulations
"""

import json
import logging
import sys
import subprocess
from pathlib import Path
from multiprocessing import Process

# Setup paths
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from dashboards.simulation_dashboard import run_dashboard

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def start_dashboard_process(sim_id: str, port: int):
    """Start a dashboard in a separate process"""
    logger.info(f"Starting dashboard for {sim_id} on port {port}")
    run_dashboard(sim_id, port)


def main():
    """Start all 4 simulation dashboards"""
    # Load config to get port mappings
    config_path = BASE_DIR / 'config' / 'simulation_config.json'
    with open(config_path, 'r') as f:
        config = json.load(f)

    simulations = config.get('simulations', {})

    processes = []

    for sim_id, sim_config in simulations.items():
        if sim_config.get('enabled', True):
            port = sim_config.get('port', 4001)
            name = sim_config.get('name', sim_id)

            p = Process(
                target=start_dashboard_process,
                args=(sim_id, port),
                name=f"dashboard_{sim_id}"
            )
            processes.append(p)
            logger.info(f"Prepared dashboard: {name} -> http://localhost:{port}")

    # Start all processes
    for p in processes:
        p.start()
        logger.info(f"Started {p.name}")

    print("\n" + "=" * 60)
    print("VSR Simulation Dashboards Started")
    print("=" * 60)
    print(f"  Sim 1 (Long + KC Lower):      http://localhost:4001")
    print(f"  Sim 2 (Long + PSAR):          http://localhost:4002")
    print(f"  Sim 3 (Short + KC Upper):     http://localhost:4003")
    print(f"  Sim 4 (Short + PSAR):         http://localhost:4004")
    print("=" * 60)
    print("Press Ctrl+C to stop all dashboards\n")

    try:
        # Wait for all processes
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        logger.info("Shutting down dashboards...")
        for p in processes:
            p.terminate()
            p.join(timeout=5)
        logger.info("All dashboards stopped")


if __name__ == '__main__':
    main()
