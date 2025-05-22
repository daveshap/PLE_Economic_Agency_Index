#!/usr/bin/env python3
"""
Script to print available BEA datasets using the BEA API key from .env
"""
import os
import requests
from dotenv import load_dotenv

BEA_API_URL = "https://apps.bea.gov/api/data/"


def main():
    load_dotenv()
    api_key = os.getenv("BEA_API_KEY")
    if not api_key:
        print("BEA_API_KEY not found in environment.")
        return

    params = {
        "method": "GETDATASETLIST",
        "UserID": api_key,
        "ResultFormat": "JSON"
    }
    print("Requesting BEA dataset list...")
    response = requests.get(BEA_API_URL, params=params)
    try:
        response.raise_for_status()
        data = response.json()
        datasets = data.get("BEAAPI", {}).get("Results", {}).get("Dataset", [])
        if not datasets:
            print("No datasets found or unexpected response:", data)
            return
        print("Available BEA datasets:")
        for ds in datasets:
            print(f"- {ds.get('DatasetName')}: {ds.get('DatasetDescription')}")
    except Exception as e:
        print("Error fetching dataset list:", e)
        print("Response:", response.text)

if __name__ == "__main__":
    main() 