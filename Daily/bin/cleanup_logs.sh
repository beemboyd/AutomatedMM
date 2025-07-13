#!/bin/bash

# Log Cleanup Script for SL_watchdog logs
# This script provides various options to manage log file sizes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/../logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}          SL_Watchdog Log Cleanup Utility${NC}"
echo -e "${BLUE}============================================================${NC}"

# Function to display log file sizes
show_log_sizes() {
    echo -e "\n${YELLOW}Current log file sizes:${NC}"
    echo "----------------------------------------"
    
    for user_dir in "$LOG_DIR"/*/; do
        if [ -d "$user_dir" ]; then
            user=$(basename "$user_dir")
            log_file="$user_dir/SL_watchdog_${user}.log"
            
            if [ -f "$log_file" ]; then
                size=$(du -h "$log_file" 2>/dev/null | cut -f1)
                lines=$(wc -l < "$log_file" 2>/dev/null)
                echo -e "${GREEN}$user${NC}: $size (${lines} lines)"
            fi
        fi
    done
    echo "----------------------------------------"
}

# Function to archive old logs
archive_logs() {
    echo -e "\n${YELLOW}Archiving logs older than 7 days...${NC}"
    
    for user_dir in "$LOG_DIR"/*/; do
        if [ -d "$user_dir" ]; then
            user=$(basename "$user_dir")
            log_file="$user_dir/SL_watchdog_${user}.log"
            
            if [ -f "$log_file" ]; then
                # Create archive directory
                archive_dir="$user_dir/archive"
                mkdir -p "$archive_dir"
                
                # Archive with timestamp
                timestamp=$(date +%Y%m%d_%H%M%S)
                archive_name="SL_watchdog_${user}_${timestamp}.log.gz"
                
                # Keep last 1000 lines in current file, archive the rest
                tail -n 1000 "$log_file" > "$log_file.tmp"
                head -n -1000 "$log_file" | gzip > "$archive_dir/$archive_name"
                mv "$log_file.tmp" "$log_file"
                
                echo -e "Archived: ${GREEN}$user${NC} → $archive_name"
            fi
        fi
    done
}

# Function to truncate logs
truncate_logs() {
    local keep_lines=${1:-1000}
    echo -e "\n${YELLOW}Truncating logs to last $keep_lines lines...${NC}"
    
    for user_dir in "$LOG_DIR"/*/; do
        if [ -d "$user_dir" ]; then
            user=$(basename "$user_dir")
            log_file="$user_dir/SL_watchdog_${user}.log"
            
            if [ -f "$log_file" ]; then
                # Keep only last N lines
                tail -n "$keep_lines" "$log_file" > "$log_file.tmp"
                mv "$log_file.tmp" "$log_file"
                echo -e "Truncated: ${GREEN}$user${NC} log"
            fi
        fi
    done
}

# Function to delete old archived logs
cleanup_archives() {
    local days=${1:-30}
    echo -e "\n${YELLOW}Deleting archived logs older than $days days...${NC}"
    
    for user_dir in "$LOG_DIR"/*/; do
        if [ -d "$user_dir/archive" ]; then
            user=$(basename "$user_dir")
            count=$(find "$user_dir/archive" -name "*.log.gz" -mtime +$days -delete -print | wc -l)
            if [ $count -gt 0 ]; then
                echo -e "Deleted $count old archives for ${GREEN}$user${NC}"
            fi
        fi
    done
}

# Function to rotate logs
rotate_logs() {
    echo -e "\n${YELLOW}Rotating logs...${NC}"
    
    for user_dir in "$LOG_DIR"/*/; do
        if [ -d "$user_dir" ]; then
            user=$(basename "$user_dir")
            log_file="$user_dir/SL_watchdog_${user}.log"
            
            if [ -f "$log_file" ]; then
                timestamp=$(date +%Y%m%d_%H%M%S)
                backup_file="$user_dir/SL_watchdog_${user}_${timestamp}.log"
                
                # Move current log to backup
                mv "$log_file" "$backup_file"
                
                # Create new empty log file
                touch "$log_file"
                
                # Compress the backup
                gzip "$backup_file"
                
                echo -e "Rotated: ${GREEN}$user${NC} → SL_watchdog_${user}_${timestamp}.log.gz"
            fi
        fi
    done
}

# Main menu
show_menu() {
    echo -e "\n${BLUE}Select an option:${NC}"
    echo "1. Show current log sizes"
    echo "2. Archive logs (keep last 1000 lines)"
    echo "3. Truncate logs to last N lines"
    echo "4. Rotate logs (backup and start fresh)"
    echo "5. Clean up old archives (>30 days)"
    echo "6. Full cleanup (archive + cleanup old)"
    echo "0. Exit"
    echo -n "Choice: "
}

# Initial display
show_log_sizes

# Main loop
while true; do
    show_menu
    read -r choice
    
    case $choice in
        1)
            show_log_sizes
            ;;
        2)
            archive_logs
            show_log_sizes
            ;;
        3)
            echo -n "Keep how many lines? (default: 1000): "
            read -r lines
            lines=${lines:-1000}
            truncate_logs "$lines"
            show_log_sizes
            ;;
        4)
            echo -e "\n${RED}Warning: This will backup current logs and start fresh.${NC}"
            echo -n "Continue? (y/n): "
            read -r confirm
            if [[ $confirm == "y" || $confirm == "Y" ]]; then
                rotate_logs
                show_log_sizes
            fi
            ;;
        5)
            echo -n "Delete archives older than how many days? (default: 30): "
            read -r days
            days=${days:-30}
            cleanup_archives "$days"
            ;;
        6)
            echo -e "\n${YELLOW}Performing full cleanup...${NC}"
            archive_logs
            cleanup_archives 30
            show_log_sizes
            ;;
        0)
            echo -e "\n${GREEN}Exiting...${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            ;;
    esac
done