#!/bin/bash
# Script to verify the golden copy integrity before and after operations

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

US_TS_DIR="/Users/maverick/PycharmProjects/US-TS"
CHECKSUM_FILE="/tmp/us_ts_golden_checksum.txt"

echo -e "${GREEN}=== Golden Copy Verification Tool ===${NC}"

# Function to generate checksums
generate_checksums() {
    echo -e "${YELLOW}Generating checksums for golden copy...${NC}"
    cd "$US_TS_DIR"
    
    # Generate checksums for all Python files and configs
    find . -type f \( -name "*.py" -o -name "*.json" -o -name "*.ini" -o -name "*.plist" \) \
        -not -path "./.git/*" -not -path "./venv/*" -not -path "./__pycache__/*" \
        -exec md5sum {} \; | sort > "$CHECKSUM_FILE"
    
    echo -e "${GREEN}Checksums saved to: $CHECKSUM_FILE${NC}"
    echo "Total files checksummed: $(wc -l < "$CHECKSUM_FILE")"
}

# Function to verify checksums
verify_checksums() {
    echo -e "${YELLOW}Verifying golden copy integrity...${NC}"
    cd "$US_TS_DIR"
    
    if [ ! -f "$CHECKSUM_FILE" ]; then
        echo -e "${RED}No baseline checksum found. Run with 'baseline' first.${NC}"
        exit 1
    fi
    
    # Generate current checksums
    TEMP_CHECKSUM="/tmp/us_ts_current_checksum.txt"
    find . -type f \( -name "*.py" -o -name "*.json" -o -name "*.ini" -o -name "*.plist" \) \
        -not -path "./.git/*" -not -path "./venv/*" -not -path "./__pycache__/*" \
        -exec md5sum {} \; | sort > "$TEMP_CHECKSUM"
    
    # Compare checksums
    if diff -q "$CHECKSUM_FILE" "$TEMP_CHECKSUM" > /dev/null; then
        echo -e "${GREEN}✅ Golden copy is intact! No files have been modified.${NC}"
    else
        echo -e "${RED}❌ Golden copy has been modified!${NC}"
        echo -e "${YELLOW}Modified files:${NC}"
        diff "$CHECKSUM_FILE" "$TEMP_CHECKSUM" | grep "^[<>]" | head -20
    fi
    
    rm -f "$TEMP_CHECKSUM"
}

# Main logic
case "${1:-verify}" in
    baseline)
        generate_checksums
        ;;
    verify)
        verify_checksums
        ;;
    *)
        echo "Usage: $0 [baseline|verify]"
        echo "  baseline - Create baseline checksums"
        echo "  verify   - Verify against baseline"
        exit 1
        ;;
esac