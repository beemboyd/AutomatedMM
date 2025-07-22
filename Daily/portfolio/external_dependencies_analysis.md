# External Dependencies Analysis for Daily, ML, and Market_Regime Folders

## Summary
This analysis identifies all import statements in the Daily, ML, and Market_Regime folders that reference files outside these folders, which would prevent them from being self-contained.

## Key Findings

### 1. sys.path Modifications
Most files that reference external dependencies add parent directories to sys.path using one of these patterns:
- `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))` - Goes up 3 levels to project root
- `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))` - Goes up 2 levels
- `sys.path.append(...)` - Similar variations

### 2. External Dependencies by Folder

#### Daily Folder External Dependencies:
1. **user_context_manager** - Referenced in 30+ files
   - Location: Project root directory
   - Used for: User authentication and context management
   - Example files:
     - Daily/trading/place_orders_daily.py
     - Daily/trading/place_orders_FNO.py
     - Daily/portfolio/SL_watchdog.py
     - Daily/services/vsr_anomaly_detector.py

2. **kiteconnect** - Referenced in 50+ files
   - Location: External package (pip install)
   - Used for: Trading API connections
   - Found in most trading, scanner, and portfolio files

3. **utils** - Referenced in 1 file
   - Location: Project root directory
   - File: Daily/MCP/portfolio_mcp_server.py

#### ML Folder External Dependencies:
1. **kiteconnect** - Referenced in 5 files
   - Files:
     - ML/winner_performance_analyzer_optimized.py
     - ML/winner_performance_analyzer.py
     - ML/test_sma_data.py
     - ML/test_kite_connection.py
     - ML/winner_performance_analyzer_simple.py

2. **Daily modules** - Many ML files import from Daily folder
   - Common pattern: Adding project root to sys.path to access Daily modules

#### Market_Regime Folder:
- **No external dependencies found!**
- The Market_Regime folder appears to be self-contained
- No sys.path modifications
- No imports from parent directories
- No imports of user_context_manager or kiteconnect

### 3. Implications for Making Folders Self-Contained

To make these folders truly self-contained, the following would need to be addressed:

1. **Copy user_context_manager module** into each folder that needs it (Daily and possibly ML)
2. **Handle kiteconnect dependency** - This is an external package, so it would remain as a pip dependency
3. **Copy any utils functions** needed by Daily/MCP/portfolio_mcp_server.py
4. **Update import statements** to use local copies instead of parent directory imports
5. **Remove all sys.path modifications** that add parent directories

### 4. Files with Most External Dependencies

#### Daily Folder - Files requiring significant changes:
- All files in Daily/trading/ (10+ files)
- All files in Daily/portfolio/ (10+ files)
- Most files in Daily/scanners/ (20+ files)
- Daily/services/vsr_anomaly_detector.py
- Daily/services/vsr_tracker_service.py

#### ML Folder - Files requiring changes:
- All files with kiteconnect imports (5 files)
- Most analysis scripts that import from Daily folder

#### Market_Regime Folder:
- Already self-contained!

## Conclusion

The Market_Regime folder is already self-contained and can be moved as-is. The Daily and ML folders have significant external dependencies, primarily:
1. user_context_manager (authentication/context management)
2. kiteconnect (external trading API)
3. Cross-folder imports (ML importing from Daily)

Making Daily and ML self-contained would require copying the user_context_manager module into each folder and updating all import statements. The kiteconnect dependency would remain as an external package requirement.