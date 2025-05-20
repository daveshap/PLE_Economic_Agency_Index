#!/usr/bin/env python3
"""
Data processing script for the Economic Agency Index Dashboard.
This script processes raw data and calculates EAI scores.
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import yaml
from tqdm import tqdm
import geopandas as gpd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from dotenv import load_dotenv
from app.models.eai import County, EAIScore, EAIMetadata

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataProcessor:
    """Class to handle data processing and EAI calculation."""
    
    def __init__(self):
        """Initialize the processor with configuration."""
        load_dotenv()
        
        # Load configuration
        config_path = project_root / "config.yaml"
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        # Set up directories
        self.raw_dir = project_root / self.config["processing"]["raw_dir"]
        self.processed_dir = project_root / self.config["processing"]["processed_dir"]
        self.interim_dir = project_root / self.config["processing"]["interim_dir"]
        
        for directory in [self.processed_dir, self.interim_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize database session
        self.engine = create_engine(self._get_database_url())
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def _get_database_url(self) -> str:
        """Get database URL from environment variables."""
        required_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    
    def load_bea_data(self) -> pd.DataFrame:
        """Load and process BEA data."""
        logger.info("Loading BEA data...")
        
        # Find the most recent BEA data file
        bea_files = list(self.raw_dir.glob("bea_sainc7_*.parquet"))
        if not bea_files:
            raise FileNotFoundError("No BEA data files found")
        
        latest_file = max(bea_files, key=lambda x: x.stat().st_mtime)
        df = pd.read_parquet(latest_file)
        
        # Process the data
        df = df.pivot_table(
            index=['GeoFips', 'Year'],
            columns='LineCode',
            values='DataValue',
            aggfunc='first'
        ).reset_index()
        
        # Rename columns based on configuration
        line_codes = self.config["data_sources"]["bea"]["tables"]["sainc7"]["lines"]
        column_map = {str(v): k for k, v in line_codes.items()}
        df = df.rename(columns=column_map)
        
        return df
    
    def load_irs_data(self) -> pd.DataFrame:
        """Load and process IRS data."""
        logger.info("Loading IRS data...")
        
        # Find the most recent IRS data file
        irs_files = list(self.raw_dir.glob("irs_county_*.xlsx"))
        if not irs_files:
            raise FileNotFoundError("No IRS data files found")
        
        latest_file = max(irs_files, key=lambda x: x.stat().st_mtime)
        df = pd.read_excel(latest_file)
        
        # Process the data (specific processing will depend on IRS file structure)
        # This is a placeholder - adjust based on actual IRS data format
        df = df.rename(columns={
            'FIPS': 'GeoFips',
            'Year': 'Year',
            # Add other column mappings as needed
        })
        
        return df
    
    def load_census_data(self) -> gpd.GeoDataFrame:
        """Load and process Census TIGER data."""
        logger.info("Loading Census TIGER data...")
        
        # Find the most recent Census data directory
        census_dir = self.raw_dir / "census_tiger"
        if not census_dir.exists():
            raise FileNotFoundError("No Census TIGER data found")
        
        # Load the shapefile
        gdf = gpd.read_file(census_dir / "tl_2023_us_county.shp")
        
        # Process the data
        gdf = gdf.rename(columns={
            'GEOID': 'GeoFips',
            'NAME': 'name',
            'STATEFP': 'state'
        })
        
        # Calculate centroids
        gdf['centroid_lat'] = gdf.geometry.centroid.y
        gdf['centroid_lon'] = gdf.geometry.centroid.x
        
        return gdf
    
    def calculate_eai_scores(self, bea_data: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """Calculate EAI scores from BEA data."""
        logger.info("Calculating EAI scores...")
        
        # Calculate income shares
        df = bea_data.copy()
        df['total_income'] = df[['earned_income', 'property_income', 'transfers']].sum(axis=1)
        
        for col in ['earned_income', 'property_income', 'transfers']:
            df[f'{col}_share'] = df[col] / df['total_income']
        
        # Calculate z-scores for each component
        components = ['earned_income_share', 'property_income_share', 'transfers_share']
        metadata = {}
        
        for year in df['Year'].unique():
            year_data = df[df['Year'] == year]
            
            # Calculate means and standard deviations
            year_metadata = {
                'mean_' + col: year_data[col].mean() for col in components
            }
            year_metadata.update({
                'std_' + col: year_data[col].std() for col in components
            })
            year_metadata['total_counties'] = len(year_data)
            
            # Store metadata
            metadata[year] = year_metadata
            
            # Calculate z-scores
            for col in components:
                df.loc[df['Year'] == year, f'{col}_zscore'] = (
                    (df.loc[df['Year'] == year, col] - year_metadata[f'mean_{col}']) /
                    year_metadata[f'std_{col}']
                )
        
        # Calculate EAI score
        df['eai_score'] = (
            df['earned_income_share_zscore'] +
            df['property_income_share_zscore'] -
            df['transfers_share_zscore']
        ) / np.sqrt(3)
        
        return df, metadata
    
    def save_to_database(self, eai_data: pd.DataFrame, metadata: Dict,
                        census_data: gpd.GeoDataFrame):
        """Save processed data to database."""
        logger.info("Saving data to database...")
        
        try:
            # Save county data
            counties = []
            for _, row in census_data.iterrows():
                county = County(
                    fips=row['GeoFips'],
                    name=row['name'],
                    state=row['state'],
                    geometry=row.geometry.to_json(),
                    centroid_lat=row['centroid_lat'],
                    centroid_lon=row['centroid_lon']
                )
                counties.append(county)
            
            self.session.bulk_save_objects(counties)
            self.session.commit()
            
            # Save EAI scores
            scores = []
            for _, row in eai_data.iterrows():
                score = EAIScore(
                    fips=row['GeoFips'],
                    year=row['Year'],
                    earned_income=row['earned_income'],
                    property_income=row['property_income'],
                    transfers=row['transfers'],
                    total_income=row['total_income'],
                    eai_score=row['eai_score'],
                    earned_share=row['earned_income_share'],
                    property_share=row['property_income_share'],
                    transfer_share=row['transfers_share']
                )
                scores.append(score)
            
            self.session.bulk_save_objects(scores)
            
            # Save metadata
            for year, year_metadata in metadata.items():
                meta = EAIMetadata(
                    year=year,
                    calculation_date=datetime.utcnow().date(),
                    **year_metadata
                )
                self.session.add(meta)
            
            self.session.commit()
            logger.info("Successfully saved data to database")
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error saving to database: {e}")
            raise
    
    def process_all(self) -> bool:
        """Process all data sources and calculate EAI scores."""
        try:
            # Load data
            bea_data = self.load_bea_data()
            irs_data = self.load_irs_data()  # For backup if needed
            census_data = self.load_census_data()
            
            # Calculate EAI scores
            eai_data, metadata = self.calculate_eai_scores(bea_data)
            
            # Save to database
            self.save_to_database(eai_data, metadata, census_data)
            
            # Save processed data to parquet
            output_file = self.processed_dir / f"eai_scores_{datetime.now().strftime('%Y%m%d')}.parquet"
            eai_data.to_parquet(output_file)
            logger.info(f"Saved processed data to {output_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing data: {e}")
            return False

def main():
    """Main function to run the data processing."""
    try:
        logger.info("Starting data processing...")
        processor = DataProcessor()
        
        if processor.process_all():
            logger.info("Data processing completed successfully")
            sys.exit(0)
        else:
            logger.error("Data processing completed with errors")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Data processing failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 