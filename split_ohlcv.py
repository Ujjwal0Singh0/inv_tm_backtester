import pandas as pd
import os

# Input and output paths
INPUT_FILE = 'input_ohlcv/all_ohlcv.csv'
OUTPUT_DIR = 'split_ohlcv_data'

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"Reading {INPUT_FILE}...")
# Read the CSV with multi-level headers
df = pd.read_csv(INPUT_FILE, header=[0, 1], index_col=0)

print(f"Data shape: {df.shape}")
print(f"Columns (first 5): {df.columns[:5].tolist()}")

# Extract unique attributes from the second level of headers
attributes = df.columns.get_level_values(1).unique().tolist()
print(f"\nFound attributes: {attributes}")

# Split and save each attribute
for attr in attributes:
    print(f"\nProcessing '{attr}'...")
    
    # Extract all columns with this attribute
    attr_df = df.xs(attr, level=1, axis=1)
    
    # Save to file
    output_file = os.path.join(OUTPUT_DIR, f'all_{attr}.csv')
    attr_df.to_csv(output_file)
    
    print(f"  ✅ Saved {output_file}")
    print(f"     Shape: {attr_df.shape}")
    print(f"     Columns: {list(attr_df.columns[:3])}..." if len(attr_df.columns) > 3 else f"     Columns: {list(attr_df.columns)}")

# Also save the complete file to split_ohlcv_data for consistency
complete_output = os.path.join(OUTPUT_DIR, 'all_ohlcv.csv')
df.to_csv(complete_output)
print(f"\n✅ Also saved complete file to {complete_output}")

print("\n🎉 All files split successfully!")
