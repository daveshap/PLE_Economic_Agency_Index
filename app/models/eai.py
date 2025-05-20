from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, Float, String, Date, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class County(Base):
    """County model for storing county information."""
    __tablename__ = "counties"

    fips = Column(String(5), primary_key=True)
    name = Column(String(100), nullable=False)
    state = Column(String(2), nullable=False)
    geometry = Column(String, nullable=True)  # GeoJSON string
    centroid_lat = Column(Float, nullable=True)
    centroid_lon = Column(Float, nullable=True)
    created_at = Column(Date, default=datetime.utcnow)
    updated_at = Column(Date, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    eai_scores = relationship("EAIScore", back_populates="county")

    __table_args__ = (
        Index("idx_county_state", "state"),
        Index("idx_county_name", "name"),
    )

class EAIScore(Base):
    """Economic Agency Index score model."""
    __tablename__ = "eai_scores"

    id = Column(Integer, primary_key=True)
    fips = Column(String(5), ForeignKey("counties.fips"), nullable=False)
    year = Column(Integer, nullable=False)
    earned_income = Column(Float, nullable=False)
    property_income = Column(Float, nullable=False)
    transfers = Column(Float, nullable=False)
    total_income = Column(Float, nullable=False)
    eai_score = Column(Float, nullable=False)
    earned_share = Column(Float, nullable=False)
    property_share = Column(Float, nullable=False)
    transfer_share = Column(Float, nullable=False)
    created_at = Column(Date, default=datetime.utcnow)
    updated_at = Column(Date, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    county = relationship("County", back_populates="eai_scores")

    __table_args__ = (
        Index("idx_eai_fips_year", "fips", "year", unique=True),
        Index("idx_eai_year", "year"),
    )

class DataSource(Base):
    """Model for tracking data source updates."""
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True)
    source_name = Column(String(50), nullable=False)
    last_update = Column(Date, nullable=False)
    status = Column(String(20), nullable=False)  # 'success', 'failed', 'pending'
    records_processed = Column(Integer, nullable=True)
    error_message = Column(String(500), nullable=True)
    created_at = Column(Date, default=datetime.utcnow)
    updated_at = Column(Date, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_source_name", "source_name"),
        Index("idx_source_status", "status"),
    )

class EAIMetadata(Base):
    """Model for storing EAI calculation metadata."""
    __tablename__ = "eai_metadata"

    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False)
    calculation_date = Column(Date, nullable=False)
    mean_earned = Column(Float, nullable=False)
    mean_property = Column(Float, nullable=False)
    mean_transfer = Column(Float, nullable=False)
    std_earned = Column(Float, nullable=False)
    std_property = Column(Float, nullable=False)
    std_transfer = Column(Float, nullable=False)
    total_counties = Column(Integer, nullable=False)
    created_at = Column(Date, default=datetime.utcnow)
    updated_at = Column(Date, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_metadata_year", "year", unique=True),
    ) 