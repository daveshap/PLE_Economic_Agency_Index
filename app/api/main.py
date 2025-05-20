"""
FastAPI backend for the Economic Agency Index Dashboard.
"""

import os
from typing import List, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
import pandas as pd
import geopandas as gpd
from dotenv import load_dotenv
import yaml
from pathlib import Path

from app.models.eai import County, EAIScore, EAIMetadata
from app.api.database import get_db, engine

# Load configuration
project_root = Path(__file__).parent.parent.parent
with open(project_root / "config.yaml") as f:
    config = yaml.safe_load(f)

# Initialize FastAPI app
app = FastAPI(
    title="Economic Agency Index API",
    description="API for the Economic Agency Index Dashboard",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config["api"]["cors_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "name": "Economic Agency Index API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/counties")
async def get_counties(
    state: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of counties with optional state filter."""
    query = db.query(County)
    if state:
        query = query.filter(County.state == state)
    
    counties = query.all()
    return [
        {
            "fips": c.fips,
            "name": c.name,
            "state": c.state,
            "centroid": {"lat": c.centroid_lat, "lon": c.centroid_lon}
        }
        for c in counties
    ]

@app.get("/eai/{fips}")
async def get_county_eai(
    fips: str,
    start_year: Optional[int] = Query(None, ge=1990),
    end_year: Optional[int] = Query(None, le=datetime.now().year),
    db: Session = Depends(get_db)
):
    """Get EAI scores for a specific county."""
    query = db.query(EAIScore).filter(EAIScore.fips == fips)
    
    if start_year:
        query = query.filter(EAIScore.year >= start_year)
    if end_year:
        query = query.filter(EAIScore.year <= end_year)
    
    scores = query.order_by(EAIScore.year).all()
    
    if not scores:
        raise HTTPException(status_code=404, detail="County not found or no data available")
    
    return [
        {
            "year": s.year,
            "eai_score": s.eai_score,
            "earned_share": s.earned_share,
            "property_share": s.property_share,
            "transfer_share": s.transfer_share,
            "total_income": s.total_income
        }
        for s in scores
    ]

@app.get("/eai/year/{year}")
async def get_year_eai(
    year: int,
    state: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get EAI scores for all counties in a specific year."""
    query = db.query(
        EAIScore, County
    ).join(
        County, EAIScore.fips == County.fips
    ).filter(
        EAIScore.year == year
    )
    
    if state:
        query = query.filter(County.state == state)
    
    results = query.all()
    
    if not results:
        raise HTTPException(status_code=404, detail="No data available for specified year")
    
    return [
        {
            "fips": r.EAIScore.fips,
            "name": r.County.name,
            "state": r.County.state,
            "eai_score": r.EAIScore.eai_score,
            "earned_share": r.EAIScore.earned_share,
            "property_share": r.EAIScore.property_share,
            "transfer_share": r.EAIScore.transfer_share,
            "total_income": r.EAIScore.total_income,
            "geometry": r.County.geometry
        }
        for r in results
    ]

@app.get("/metadata/year/{year}")
async def get_year_metadata(
    year: int,
    db: Session = Depends(get_db)
):
    """Get metadata for a specific year's EAI calculations."""
    metadata = db.query(EAIMetadata).filter(EAIMetadata.year == year).first()
    
    if not metadata:
        raise HTTPException(status_code=404, detail="No metadata available for specified year")
    
    return {
        "year": metadata.year,
        "calculation_date": metadata.calculation_date,
        "mean_earned": metadata.mean_earned,
        "mean_property": metadata.mean_property,
        "mean_transfer": metadata.mean_transfer,
        "std_earned": metadata.std_earned,
        "std_property": metadata.std_property,
        "std_transfer": metadata.std_transfer,
        "total_counties": metadata.total_counties
    }

@app.get("/states")
async def get_states(db: Session = Depends(get_db)):
    """Get list of states with county counts."""
    states = db.query(
        County.state,
        func.count(County.fips).label("county_count")
    ).group_by(
        County.state
    ).all()
    
    return [
        {
            "state": s.state,
            "county_count": s.county_count
        }
        for s in states
    ]

@app.get("/years")
async def get_available_years(db: Session = Depends(get_db)):
    """Get list of years with available data."""
    years = db.query(
        EAIScore.year
    ).distinct().order_by(
        EAIScore.year
    ).all()
    
    return [y.year for y in years]

@app.get("/download/eai")
async def download_eai_data(
    start_year: Optional[int] = Query(None, ge=1990),
    end_year: Optional[int] = Query(None, le=datetime.now().year),
    state: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Download EAI data as CSV."""
    query = db.query(
        EAIScore, County
    ).join(
        County, EAIScore.fips == County.fips
    )
    
    if start_year:
        query = query.filter(EAIScore.year >= start_year)
    if end_year:
        query = query.filter(EAIScore.year <= end_year)
    if state:
        query = query.filter(County.state == state)
    
    results = query.all()
    
    if not results:
        raise HTTPException(status_code=404, detail="No data available for specified parameters")
    
    # Convert to DataFrame
    data = []
    for r in results:
        data.append({
            "fips": r.EAIScore.fips,
            "county": r.County.name,
            "state": r.County.state,
            "year": r.EAIScore.year,
            "eai_score": r.EAIScore.eai_score,
            "earned_share": r.EAIScore.earned_share,
            "property_share": r.EAIScore.property_share,
            "transfer_share": r.EAIScore.transfer_share,
            "total_income": r.EAIScore.total_income
        })
    
    df = pd.DataFrame(data)
    
    # Return as CSV
    return {
        "filename": f"eai_data_{datetime.now().strftime('%Y%m%d')}.csv",
        "content": df.to_csv(index=False)
    } 