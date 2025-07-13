#!/bin/bash

# Simple wrapper script for the new multi-user watchdog manager
# Starts watchdogs for all users with active orders

cd "$(dirname "${BASH_SOURCE[0]}")"
./manage_watchdogs.sh start "$@"