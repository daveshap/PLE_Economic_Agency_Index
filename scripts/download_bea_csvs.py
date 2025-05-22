"""
Download and extract BEA county-level CSV ZIP files (CAINC4 and CAINC35), printing the CSVs inside each.
"""

import os
import requests
import pandas as pd
from pathlib import Path
import json
from datetime import datetime
import time
from dotenv import load_dotenv

load_dotenv()

# Create data directory if it doesn't exist
data_dir = Path("data/raw")
data_dir.mkdir(parents=True, exist_ok=True)

# BEA API configuration
BEA_API_KEY = os.getenv("BEA_API_KEY")
if not BEA_API_KEY:
    raise ValueError("BEA_API_KEY environment variable not set")

BASE_URL = "https://apps.bea.gov/api/data"
DATASETS = {
    "CAINC4": "Regional Income & Employment",  # Personal income by county
    "CAINC35": "Local Area Personal Income",   # Personal income by metropolitan area
}

def get_parameter_values(dataset_name):
    """Get available parameter values for a dataset"""
    params = {
        "UserID": BEA_API_KEY,
        "method": "GetParameterValues",
        "datasetname": dataset_name,
        "ParameterName": "Year",
        "ResultFormat": "json"
    }
    
    response = requests.get(BASE_URL, params=params)
    if response.status_code != 200:
        print(f"Error getting parameters for {dataset_name}: {response.text}")
        return []
    
    data = response.json()
    if "BEAAPI" not in data or "Results" not in data["BEAAPI"] or "ParamValue" not in data["BEAAPI"]["Results"]:
        print(f"Unexpected API response for {dataset_name}: {json.dumps(data, indent=2)}")
        return []
    
    return [item["Key"] for item in data["BEAAPI"]["Results"]["ParamValue"]]

def download_dataset(dataset_name, years):
    """Download data for a specific dataset and years"""
    print(f"\nDownloading {dataset_name} ({DATASETS[dataset_name]})...")
    
    all_data = []
    for year in years:
        print(f"  Fetching year {year}...")
        
        params = {
            "UserID": BEA_API_KEY,
            "method": "GetData",
            "datasetname": dataset_name,
            "Year": year,
            "ResultFormat": "json"
        }
        
        # Add LineCode parameter for specific datasets
        if dataset_name == "CAINC4":
            params["LineCode"] = "1"  # Total personal income
        elif dataset_name == "CAINC35":
            params["LineCode"] = "1"  # Total personal income
        
        response = requests.get(BASE_URL, params=params)
        if response.status_code != 200:
            print(f"    Error downloading {year}: {response.text}")
            continue
        
        try:
            data = response.json()
            if "BEAAPI" not in data or "Results" not in data["BEAAPI"]:
                print(f"    Unexpected API response for {year}: {data}")
                continue
            
            # Extract the data
            results = data["BEAAPI"]["Results"]["Data"]
            if not results:
                print(f"    No data found for {year}")
                continue
            
            # Convert to DataFrame
            df = pd.DataFrame(results)
            df['Year'] = year
            all_data.append(df)
            
            # Be nice to the API
            time.sleep(0.5)
            
        except Exception as e:
            print(f"    Error processing {year}: {str(e)}")
            continue
    
    if not all_data:
        print(f"  No data downloaded for {dataset_name}")
        return
    
    # Combine all years
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Save to CSV
    output_file = data_dir / f"{dataset_name}.csv"
    combined_df.to_csv(output_file, index=False)
    print(f"  Saved {len(combined_df)} rows to {output_file}")

def get_dataset_list():
    """Print a list of available BEA API datasets."""
    params = { "UserID": BEA_API_KEY, "method": "GetDatasetList", "ResultFormat": "json" }
    resp = requests.get(BASE_URL, params=params)
    if resp.status_code != 200:
        print("Error fetching dataset list: " + resp.text)
        return
    data = resp.json()
    if "BEAAPI" not in data or "Results" not in data["BEAAPI"] or "Dataset" not in data["BEAAPI"]["Results"]:
        print("Unexpected API response for dataset list: " + json.dumps(data, indent=2))
        return
    print("Available BEA API datasets:")
    for ds in data["BEAAPI"]["Results"]["Dataset"]:
        print(f" – {ds['DatasetName']} ({ds['DatasetDescription']})")

def main():
    print("Starting BEA data download...")
    print(f"Using API key: {BEA_API_KEY[:4]}...{BEA_API_KEY[-4:]}")
    get_dataset_list()
    first_dataset = list(DATASETS.keys())[0]
    available_years = get_parameter_values(first_dataset)
    if not available_years:
        print("No years available. Check API key and internet connection.")
        return
    years_to_download = sorted(available_years)[-5:]  # Get the last 5 years
    print(f"\nDownloading data for years: {', '.join(years_to_download)}")
    for dataset_name in DATASETS:
        download_dataset(dataset_name, years_to_download)
    print("\nDownload complete!")

if __name__ == "__main__":
    main() 