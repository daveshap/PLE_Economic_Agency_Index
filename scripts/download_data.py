#!/usr/bin/env python3
"""
Data download script for the Economic Agency Index Dashboard.
This script downloads data from BEA, IRS, and Census sources.
"""

import os
import sys
import logging
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import yaml
from tqdm import tqdm
import zipfile
import io

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.eai import DataSource

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataDownloader:
    """Class to handle data downloads from various sources."""
    
    def __init__(self):
        """Initialize the downloader with configuration."""
        load_dotenv()
        
        # Load configuration
        config_path = project_root / "config.yaml"
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        # Create necessary directories
        self.raw_dir = project_root / self.config["processing"]["raw_dir"]
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database session
        self.engine = create_engine(self._get_database_url())
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Set up API keys and base URLs
        self.bea_api_key = os.getenv("BEA_API_KEY")
        if not self.bea_api_key:
            raise ValueError("BEA_API_KEY environment variable is required")
        logger.debug(f"BEA API Key (first 8 chars): {self.bea_api_key[:8]}...")
    
    def _get_database_url(self) -> str:
        """Get database URL from environment variables."""
        required_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    
    def _update_source_status(self, source_name: str, status: str, 
                            records_processed: Optional[int] = None,
                            error_message: Optional[str] = None):
        """Update the status of a data source in the database."""
        source = DataSource(
            source_name=source_name,
            last_update=datetime.utcnow().date(),
            status=status,
            records_processed=records_processed,
            error_message=error_message
        )
        self.session.add(source)
        self.session.commit()
    
    def download_bea_data(self) -> bool:
        """Download data from BEA API."""
        try:
            logger.info("Downloading BEA data...")
            base_url = self.config["data_sources"]["bea"]["base_url"]
            table = self.config["data_sources"]["bea"]["tables"]["sainc7"]
            
            # Download data for each year
            start_year = self.config["processing"]["start_year"]
            current_year = self.config["processing"]["current_year"]
            
            all_data = []
            for year in tqdm(range(start_year, current_year + 1), desc="Downloading BEA data"):
                params = {
                    "method": "GetData",
                    "datasetname": "Regional",
                    "TableName": table["name"],
                    "LineCode": ",".join(str(v) for v in table["lines"].values()),
                    "Year": str(year),
                    "GeoFips": "COUNTY",
                    "UserID": self.bea_api_key
                }
                
                logger.info(f"Requesting BEA dataset: datasetname={params['datasetname']}, TableName={params['TableName']}, LineCode={params['LineCode']}, Year={params['Year']}")
                
                response = requests.get(base_url, params=params)
                response.raise_for_status()
                
                data = response.json()
                logger.debug(f"BEA API Response: {data}")
                
                if "BEAAPI" not in data:
                    logger.error(f"Unexpected BEA API response format: {data}")
                    raise ValueError("Invalid BEA API response format")
                    
                if "Results" not in data["BEAAPI"]:
                    logger.error(f"BEA API error: {data.get('BEAAPI', {}).get('Error', 'Unknown error')}")
                    raise ValueError(f"BEA API error: {data.get('BEAAPI', {}).get('Error', 'Unknown error')}")
                    
                if "Data" not in data["BEAAPI"]["Results"]:
                    logger.error(f"BEA API response missing Data: {data['BEAAPI']['Results']}")
                    raise ValueError("BEA API response missing Data")
                
                all_data.extend(data["BEAAPI"]["Results"]["Data"])
            
            # Save to parquet file
            df = pd.DataFrame(all_data)
            output_file = self.raw_dir / f"bea_sainc7_{datetime.now().strftime('%Y%m%d')}.parquet"
            df.to_parquet(output_file)
            
            self._update_source_status("BEA", "success", len(df))
            logger.info(f"Successfully downloaded BEA data to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading BEA data: {e}")
            self._update_source_status("BEA", "failed", error_message=str(e))
            return False
    
    def download_irs_data(self) -> bool:
        """Download IRS county data."""
        try:
            logger.info("Downloading IRS data...")
            base_url = self.config["data_sources"]["irs"]["base_url"]
            
            # Download the most recent year's data
            response = requests.get(base_url)
            response.raise_for_status()
            
            # Save the Excel file
            output_file = self.raw_dir / f"irs_county_{datetime.now().strftime('%Y%m%d')}.xlsx"
            with open(output_file, 'wb') as f:
                f.write(response.content)
            
            self._update_source_status("IRS", "success")
            logger.info(f"Successfully downloaded IRS data to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading IRS data: {e}")
            self._update_source_status("IRS", "failed", error_message=str(e))
            return False
    
    def download_census_data(self) -> bool:
        """Download Census TIGER county shapefiles."""
        try:
            logger.info("Downloading Census TIGER data...")
            base_url = self.config["data_sources"]["census"]["tiger_url"]
            shapefile = self.config["data_sources"]["census"]["shapefile"]
            
            # Download the shapefile
            response = requests.get(f"{base_url}/{shapefile}")
            response.raise_for_status()
            
            # Extract the zip file
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                zip_ref.extractall(self.raw_dir / "census_tiger")
            
            self._update_source_status("Census", "success")
            logger.info("Successfully downloaded and extracted Census TIGER data")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading Census data: {e}")
            self._update_source_status("Census", "failed", error_message=str(e))
            return False
    
    def download_all(self) -> bool:
        """Download all data sources."""
        success = True
        
        # Download from each source
        if not self.download_bea_data():
            success = False
        if not self.download_irs_data():
            success = False
        if not self.download_census_data():
            success = False
        
        return success

def main():
    """Main function to run the data download process."""
    try:
        logger.info("Starting data download process...")
        downloader = DataDownloader()
        
        if downloader.download_all():
            logger.info("Data download completed successfully")
            sys.exit(0)
        else:
            logger.error("Data download completed with errors")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Data download failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 