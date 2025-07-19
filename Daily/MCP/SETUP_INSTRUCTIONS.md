# Claude Desktop MCP Integration Setup

## Prerequisites

1. Install required Python packages:
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/MCP
pip3 install -r requirements.txt
```

## Configuration Steps

### 1. Locate Claude Desktop Config File

The Claude Desktop configuration file is typically located at:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

### 2. Edit Configuration

Add the following to your `claude_desktop_config.json` file:

```json
{
  "mcpServers": {
    "india-portfolio": {
      "command": "python3",
      "args": ["/Users/maverick/PycharmProjects/India-TS/Daily/MCP/portfolio_mcp_server.py"],
      "cwd": "/Users/maverick/PycharmProjects/India-TS/Daily/MCP",
      "env": {
        "PYTHONPATH": "/Users/maverick/PycharmProjects/India-TS"
      }
    },
    "india-market": {
      "command": "python3",
      "args": ["/Users/maverick/PycharmProjects/India-TS/Daily/MCP/market_mcp_server.py"],
      "cwd": "/Users/maverick/PycharmProjects/India-TS/Daily/MCP",
      "env": {
        "PYTHONPATH": "/Users/maverick/PycharmProjects/India-TS"
      }
    }
  }
}
```

If the file already exists and has other servers configured, merge this configuration with the existing content.

**Note**: The configuration has already been added to your Claude Desktop! The servers are named:
- `india-portfolio` - For portfolio and transaction analysis
- `india-market` - For market regime and breadth analysis

### 3. Restart Claude Desktop

After updating the configuration, restart Claude Desktop for the changes to take effect.

## Usage in Claude Desktop

Once configured, you can use these servers in Claude Desktop by:

1. **Portfolio Analysis Examples:**
   - "Show me the top performing transactions this week"
   - "Analyze Som's order performance over the last 7 days"
   - "What's our portfolio's win rate and total PnL?"
   - "Get the top 10 losers this month"

2. **Market Analysis Examples:**
   - "What's the current market regime?"
   - "Show me today's market breadth indicators"
   - "How many long vs short reversal setups are there?"
   - "Are the indices above or below their SMA20?"
   - "Give me trading insights based on current market conditions"

## Troubleshooting

### Server Not Starting
1. Check Python installation: `python3 --version`
2. Verify packages are installed: `pip3 list | grep mcp`
3. Test servers manually:
   ```bash
   cd /Users/maverick/PycharmProjects/India-TS/Daily/MCP
   python3 portfolio_mcp_server.py
   ```

### No Data Returned
1. Verify data files exist in the expected locations
2. Check file permissions
3. Look at Claude Desktop logs for error messages

### Path Issues
- Ensure all paths in the config are absolute paths
- On Windows, use forward slashes or escaped backslashes

## Testing the Integration

After setup, you can test by asking Claude Desktop:
- "Using the portfolio-analysis server, show me recent transactions"
- "Using the market-analysis server, what's the current market regime?"

The servers should automatically provide the data to Claude for analysis.