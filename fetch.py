from tvDatafeed import TvDatafeed, Interval
import pandas as pd
import os
from datetime import datetime
import re
import time
import tqdm

# Input Weights File
INPUT_WEIGHTS = "input_weights/weights.csv"

username = "rialto364@gmail.com"
password = "TradingView@@123"
tv = TvDatafeed(username, password)

def clean_symbol(symbol):
    """Cleans the symbol name to be compatible with the API."""
    return re.sub(r'[^\w]', '_', symbol)
def fill_gaps_with_boundary_mean(df):

    ffill_val = df.ffill()
    bfill_val = df.bfill()
    filled_df = (ffill_val + bfill_val) / 2
    
    # 4. Fill original NaNs (Stocks starting/ending with NaNs will remain NaN)
    return df.fillna(filled_df)
def fetch_and_save_ohlcv(symbols_input, start_date=None, end_date=None, update=False):
    # --- 1. Symbol Input Processing ---
    symbols_list = []
    if isinstance(symbols_input, list):
        print("Processing symbols from the provided list.")
        symbols_list = symbols_input
    elif isinstance(symbols_input, str):
        try:
            print(f"Reading symbols from CSV file: {symbols_input}")
            symbols_list = pd.read_csv(symbols_input)['Symbol'].tolist()
        except Exception as e:
            print(f"Error reading symbols input: {e}")
            return []
    if not symbols_list:
        print("No symbols to process.")
        return []

    # --- 2. Bar Calculation Logic ---
    n_bars = 5000
    if start_date:
        start_date_dt = pd.to_datetime(start_date)
        days_diff = (datetime.now() - start_date_dt).days
        n_bars = ((days_diff * 5) // 7) + 50
        print(f"Start date provided. Calculating required bars: approx. {n_bars}")

    data_dict = {}
    failed_symbols = []
    
    # --- 3. Data Fetching Loop with Retry Logic ---
    retries = 3 
    
    print(f"--- Fetching data for {len(symbols_list)} symbols ---")
    
    # CHANGED: Use tqdm.tqdm to access the class explicitly
    for symbol in tqdm.tqdm(symbols_list, desc="Fetching Stocks", unit="symbol"):
        for attempt in range(retries):
            try:
                cleaned_symbol = clean_symbol(symbol)
                data = tv.get_hist(symbol=cleaned_symbol, exchange='NSE', interval=Interval.in_daily, n_bars=n_bars)
                time.sleep(0.5)
                
                if data is None or data.empty:
                    # CHANGED: Use tqdm.tqdm.write
                    #tqdm.tqdm.write(f"No data for {symbol} (Attempt {attempt+1}/{retries})")
                    time.sleep(0.5) 
                    continue 

                df = pd.DataFrame(data); df.index = pd.to_datetime(df.index)
                if start_date: df = df[df.index >= pd.to_datetime(start_date)]
                if end_date: df = df[df.index <= pd.to_datetime(end_date)]

                if df.empty:
                    #tqdm.tqdm.write(f"No data for {symbol} in date range.")
                    break 
                
                # Save the data using the symbol with the .NS suffix as the key
                data_dict[symbol + ".NS"] = df[['open', 'high', 'low', 'close', 'volume']]
                
                time.sleep(1) 
                break 
                
            except Exception as e:
                #tqdm.tqdm.write(f"Error processing {symbol} (Attempt {attempt + 1}/{retries}): {e}")
                
                if "Connection to remote host was lost" in str(e) and attempt < retries - 1:
                    wait_time = (attempt + 1) * 5 
                    tqdm.tqdm.write(f"Connection lost. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    failed_symbols.append(symbol)
                    break 
            
    if not data_dict:
        print("No data was successfully fetched."); return failed_symbols

    # --- 4. Optimized Saving, Cleaning & Splitting Logic ---
    output_dir = "split_ohlcv_data"
    if not os.path.exists(output_dir): os.makedirs(output_dir)
    
    master_file_path = os.path.join(output_dir, "all_ohlcv.csv")

    try:
        print("\n--- Processing Data ---")
        
        # 1. Create a Master DataFrame from the currently fetched data (No cleaning yet)
        current_master_df = pd.concat(data_dict, axis=1)
        
        # --- FIX 1: Set index name to None immediately ---
        current_master_df.index.name = None 

        # 2. Handle Update Mode (Merge current fetch with existing file)
        if update and os.path.exists(master_file_path):
            print("Update mode active: Merging with existing Master file...")
            existing_master = pd.read_csv(master_file_path, index_col=0, parse_dates=True, header=[0, 1])
            
            # --- FIX 2: Sanitize existing data ---
            if 'Date' in existing_master.index:
                print("Removing corrupted 'Date' row from existing file...")
                existing_master = existing_master.drop('Date')
            
            # Ensure index is datetime
            existing_master.index = pd.to_datetime(existing_master.index, errors='coerce')
            existing_master = existing_master[~existing_master.index.isna()]

            # Combine: update existing values with new ones
            master_df = existing_master.combine_first(current_master_df)
            master_df.update(current_master_df) 
        else:
            master_df = current_master_df

        # --- FIX 3: Ensure index name is None for the FINAL dataframe ---
        master_df.index.name = None

        # 3. CLEANING: Fill gaps (Performed ONLY on the final, combined DataFrame)
        print("Cleaning missing values (mean of boundaries)...")
        master_df = fill_gaps_with_boundary_mean(master_df)

        # 4. Save the Consolidated Master File
        master_df.to_csv(master_file_path)
        print(f"✅ Successfully saved Cleaned Master Data to '{master_file_path}'")

        # 5. Split into individual OHLCV files
        print("Splitting Master file into individual attribute files...")
        attributes = ['open', 'high', 'low', 'close', 'volume']
        
        for attr in attributes:
            # Use xs (Cross Section) to grab all columns for a specific attribute level
            attr_df = master_df.xs(attr, axis=1, level=1)
            
            # --- FIX 4: Explicitly set index name to 'Date' for single-level files ---
            attr_df.index.name = 'Date'
            
            output_file = os.path.join(output_dir, f"all_{attr}.csv")
            attr_df.to_csv(output_file)
            print(f"   -> Saved all_{attr}.csv")

    except Exception as e:
        print(f"❌ Critical Error during save/split process: {e}")
        return failed_symbols

    print(f"\nAll files saved successfully in '{output_dir}'!")
    return failed_symbols
def smart_fetch_ohlcv(symbols_input, start_date=None, end_date=None):
    # --- 1. Process Symbol Input ---
    symbols_list = []
    if isinstance(symbols_input, list):
        print("Processing symbols from the provided list.")
        symbols_list = symbols_input
    if not symbols_list:
        print("No symbols to process.")
        return []
    
    # Add .NS suffix to symbols for comparison
    requested_symbols = set([sym + ".NS" for sym in symbols_list])
    
    # --- 2. Check if existing data file exists ---
    master_file_path = "split_ohlcv_data/all_close.csv"
    
    if not os.path.exists(master_file_path):
        print("No existing data found. Performing complete fetch...")
        return fetch_and_save_ohlcv(symbols_input, start_date, end_date, update=False)
    
    # --- 3. Read existing data ---
    try:
        existing_data = pd.read_csv(master_file_path, index_col=0, parse_dates=True)
        existing_symbols = set(existing_data.columns)
        
        # Get date range of existing data
        existing_start = existing_data.index.min()
        existing_end = existing_data.index.max()
        
        print(f"\n--- Existing Data Summary ---")
        print(f"Symbols in file: {len(existing_symbols)}")
        print(f"Date range: {existing_start.date()} to {existing_end.date()}")
        
    except Exception as e:
        print(f"Error reading existing data: {e}")
        print("Performing complete fetch...")
        return fetch_and_save_ohlcv(symbols_input, start_date, end_date, update=False)
    
    # --- 4. Check if symbols match ---
    if requested_symbols != existing_symbols:
        print(f"\n⚠️ Symbol mismatch detected!")
        print("\nPerforming complete fetch with new symbol list...")
        return fetch_and_save_ohlcv(symbols_input, start_date, end_date, update=False)
    
    # --- 5. Symbols match - check date ranges ---
    print(f"\n✅ Symbols match! Checking date ranges...")
    
    requested_start = pd.to_datetime(start_date) if start_date else None
    requested_end = pd.to_datetime(end_date) if end_date else pd.Timestamp(datetime.today())
    
    needs_fetch_before = False
    needs_fetch_after = False
    needs_clip_start = False
    needs_clip_end = False
    
    # Check if we need to fetch data before existing start
    if requested_start and requested_start < existing_start:
        needs_fetch_before = True
        print(f"📥 Need to fetch data BEFORE {existing_start.date()}")
    elif requested_start and requested_start > existing_start:
        needs_clip_start = True
        print(f"✂️ Will clip data to start from {requested_start.date()}")
    # Check if we need to fetch data after existing end
    if requested_end > existing_end:
        needs_fetch_after = True
        print(f"📥 Need to fetch data AFTER {existing_end.date()}")
    elif requested_end < existing_end:
        needs_clip_end = True
        print(f"✂️ Will clip data to end at {requested_end.date()}")
    
    # --- 6. Handle fetching and clipping ---
    failed_symbols = []
    
    # Fetch missing data before
    if needs_fetch_before:
        print(f"\n--- Fetching data from {requested_start.date()} to {existing_start.date()} ---")
        failed_before = fetch_and_save_ohlcv(
            symbols_input,
            start_date=requested_start.strftime('%Y-%m-%d'),
            end_date=(existing_start - pd.Timedelta(days=1)).strftime('%Y-%m-%d'),
            update=True
        )
        failed_symbols.extend(failed_before)
    
    # Fetch missing data after
    if needs_fetch_after:
        print(f"\n--- Fetching data from {existing_end.date()} to {requested_end.date()} ---")
        failed_after = fetch_and_save_ohlcv(
            symbols_input,
            start_date=(existing_end + pd.Timedelta(days=1)).strftime('%Y-%m-%d'),
            end_date=requested_end.strftime('%Y-%m-%d'),
            update=True
        )
        failed_symbols.extend(failed_after)
    
    # Clip data if needed
    if needs_clip_start or needs_clip_end:
        print(f"\n--- Clipping data to requested range ---")
        try:
            # Reload the master file after potential updates
            master_df = pd.read_csv("split_ohlcv_data/all_ohlcv.csv", index_col=0, parse_dates=True, header=[0, 1])
            
            # Clip to requested range
            clip_start = requested_start if requested_start else master_df.index.min()
            clip_end = requested_end if requested_end else master_df.index.max()
            
            master_df = master_df.loc[clip_start:clip_end]
            
            # Save clipped master file
            master_df.to_csv("split_ohlcv_data/all_ohlcv.csv")
            print(f"✅ Clipped master data to {master_df.index.min().date()} - {master_df.index.max().date()}")
            
            # Re-split into individual files
            print("Updating individual attribute files...")
            attributes = ['open', 'high', 'low', 'close', 'volume']
            for attr in attributes:
                attr_df = master_df.xs(attr, axis=1, level=1)
                attr_df.index.name = 'Date'
                output_file = f"split_ohlcv_data/all_{attr}.csv"
                attr_df.to_csv(output_file)
                print(f"   -> Updated all_{attr}.csv")
                
        except Exception as e:
            print(f"❌ Error during clipping: {e}")
    
    # --- 7. Report results ---
    if not needs_fetch_before and not needs_fetch_after and not needs_clip_start and not needs_clip_end:
        print(f"\n✅ All data already up to date! No fetching or clipping needed.")
    else:
        print(f"\n✅ Smart fetch completed!")
    
    # --- 8. Retry failed symbols with complete fetch ---
    if failed_symbols:
        print(f"\n⚠️ Found {len(failed_symbols)} failed symbols: {failed_symbols}")
        print(f"🔄 Retrying failed symbols with complete fetch...")
        
        retry_failed = fetch_and_save_ohlcv(
            failed_symbols,
            start_date=start_date,
            end_date=end_date,
            update=True
        )
        
        if retry_failed:
            print(f"\n❌ Still failed after retry: {retry_failed}")
            return retry_failed
        else:
            print(f"\n✅ All failed symbols successfully fetched on retry!")
            return []
    else:
        print(f"\n✅ Complete fetch successful on first try!")
        return []
    
# Read weights.csv and extract ticker symbols from columns
weights_df = pd.read_csv(INPUT_WEIGHTS)

# Ensure Date column exists and derive start/end dates
if 'Date' not in weights_df.columns:
    raise ValueError("weights.csv must contain a 'Date' column.")

date_col = pd.to_datetime(weights_df['Date'], errors='coerce')
valid_dates = date_col.dropna()
START_DATE = valid_dates.min().date().isoformat() if not valid_dates.empty else None
END_DATE = valid_dates.max().date().isoformat() if not valid_dates.empty else None

# Get all column names except 'Date'
symbols_to_fetch = [col for col in weights_df.columns if col.lower() != 'date']

# Remove .NS suffix from symbols for fetching (will be added back in fetch function)
symbols_to_fetch = [sym.replace('.NS', '') for sym in symbols_to_fetch]

print(f"Symbols extracted from weights.csv: {symbols_to_fetch}")
print(f"Date range from weights.csv -> start: {START_DATE}, end: {END_DATE}")
if __name__ == "__main__":
    failed = smart_fetch_ohlcv(symbols_to_fetch, start_date=START_DATE, end_date=END_DATE)
    if failed:
        print(f"Failed symbols: {failed}")
