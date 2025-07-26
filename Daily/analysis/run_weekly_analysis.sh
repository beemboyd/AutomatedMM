#!/bin/bash

# Week-by-week analysis for past 4 weeks
# Week 1: Jun 28 - Jul 04
# Week 2: Jul 05 - Jul 11  
# Week 3: Jul 12 - Jul 18
# Week 4: Jul 19 - Jul 25

echo "============================================================"
echo "WEEK BY WEEK REVERSAL STRATEGY ANALYSIS"
echo "============================================================"

# Week 1: Jun 28 - Jul 04
echo -e "\n\n===== WEEK 1 (Jun 28 - Jul 04) ====="
echo -e "\n--- Long Reversal ---"
python3 analysis/unified_reversal_analyzer.py --direction long --from-date 2025-06-28 --to-date 2025-07-04

echo -e "\n--- Short Reversal ---"
python3 analysis/unified_reversal_analyzer.py --direction short --from-date 2025-06-28 --to-date 2025-07-04

# Week 2: Jul 05 - Jul 11
echo -e "\n\n===== WEEK 2 (Jul 05 - Jul 11) ====="
echo -e "\n--- Long Reversal ---"
python3 analysis/unified_reversal_analyzer.py --direction long --from-date 2025-07-05 --to-date 2025-07-11

echo -e "\n--- Short Reversal ---"
python3 analysis/unified_reversal_analyzer.py --direction short --from-date 2025-07-05 --to-date 2025-07-11

# Week 3: Jul 12 - Jul 18
echo -e "\n\n===== WEEK 3 (Jul 12 - Jul 18) ====="
echo -e "\n--- Long Reversal ---"
python3 analysis/unified_reversal_analyzer.py --direction long --from-date 2025-07-12 --to-date 2025-07-18

echo -e "\n--- Short Reversal ---"
python3 analysis/unified_reversal_analyzer.py --direction short --from-date 2025-07-12 --to-date 2025-07-18

# Week 4: Jul 19 - Jul 25
echo -e "\n\n===== WEEK 4 (Jul 19 - Jul 25) ====="
echo -e "\n--- Long Reversal ---"
python3 analysis/unified_reversal_analyzer.py --direction long --from-date 2025-07-19 --to-date 2025-07-25

echo -e "\n--- Short Reversal ---"
python3 analysis/unified_reversal_analyzer.py --direction short --from-date 2025-07-19 --to-date 2025-07-25

echo -e "\n\n============================================================"
echo "ANALYSIS COMPLETE"
echo "============================================================"