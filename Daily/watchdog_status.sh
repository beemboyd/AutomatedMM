#!/bin/bash

# Simple wrapper script for the new multi-user watchdog manager
# Shows status of all watchdogs

cd "$(dirname "${BASH_SOURCE[0]}")"
./manage_watchdogs.sh status "$@"