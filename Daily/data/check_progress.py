import pandas as pd

# Check the temporary file
temp_file = "Ticker_with_Sector_temp.xlsx"
df = pd.read_excel(temp_file)

print(f"Total tickers: {len(df)}")
print(f"Sectors found: {df['Sector'].notna().sum()}")
print(f"Missing sectors: {df['Sector'].isna().sum()}")
print(f"\nFirst 10 tickers with sectors:")
print(df[df['Sector'].notna()][['Ticker', 'Sector']].head(10))
print(f"\nSample of tickers missing sectors:")
print(df[df['Sector'].isna()]['Ticker'].head(10).tolist())