"""
Streamlit dashboard for the Economic Agency Index.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
from datetime import datetime
import yaml
from pathlib import Path
import altair as alt
import numpy as np

# Load configuration
project_root = Path(__file__).parent.parent.parent
with open(project_root / "config.yaml") as f:
    config = yaml.safe_load(f)

# API configuration
API_BASE_URL = f"http://localhost:{config['api']['api_port']}"

# Page configuration
st.set_page_config(
    page_title="Economic Agency Index Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# Helper functions
def fetch_api_data(endpoint: str, params: dict = None) -> dict:
    """Fetch data from the API."""
    try:
        response = requests.get(f"{API_BASE_URL}/{endpoint}", params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data: {e}")
        return None

def create_choropleth_map(data: list, year: int) -> go.Figure:
    """Create a choropleth map of EAI scores."""
    # Convert data to DataFrame
    df = pd.DataFrame(data)
    
    # Create the choropleth map
    fig = px.choropleth(
        df,
        geojson=json.loads(df['geometry'].iloc[0]),  # Use first geometry as template
        locations='fips',
        color='eai_score',
        color_continuous_scale=config['visualization']['map']['colors'],
        range_color=(-2, 2),  # Adjust based on your data
        scope="usa",
        title=f"Economic Agency Index - {year}",
        labels={'eai_score': 'EAI Score'},
        hover_data={
            'name': True,
            'state': True,
            'eai_score': ':.2f',
            'earned_share': ':.1%',
            'property_share': ':.1%',
            'transfer_share': ':.1%'
        }
    )
    
    # Update layout
    fig.update_layout(
        geo=dict(
            showlakes=True,
            lakecolor='rgb(255, 255, 255)',
            showsubunits=True,
            subunitcolor='rgb(217, 217, 217)',
        ),
        margin={"r":0,"t":30,"l":0,"b":0},
        height=600
    )
    
    return fig

def create_time_series(data: list, county_name: str) -> go.Figure:
    """Create a time series plot of EAI components."""
    df = pd.DataFrame(data)
    
    fig = go.Figure()
    
    # Add traces for each component
    fig.add_trace(go.Scatter(
        x=df['year'],
        y=df['earned_share'],
        name='Earned Income',
        line=dict(color='#2ecc71')
    ))
    
    fig.add_trace(go.Scatter(
        x=df['year'],
        y=df['property_share'],
        name='Property Income',
        line=dict(color='#3498db')
    ))
    
    fig.add_trace(go.Scatter(
        x=df['year'],
        y=df['transfer_share'],
        name='Transfers',
        line=dict(color='#e74c3c')
    ))
    
    fig.add_trace(go.Scatter(
        x=df['year'],
        y=df['eai_score'],
        name='EAI Score',
        line=dict(color='#2c3e50', width=2)
    ))
    
    # Update layout
    fig.update_layout(
        title=f"Economic Agency Index Components - {county_name}",
        xaxis_title="Year",
        yaxis_title="Share / Score",
        hovermode="x unified",
        height=400
    )
    
    return fig

# Sidebar
st.sidebar.title("Economic Agency Index Dashboard")
st.sidebar.markdown("---")

# Year selection
years = fetch_api_data("years")
if years:
    selected_year = st.sidebar.selectbox(
        "Select Year",
        years,
        index=len(years)-1
    )
else:
    st.error("Could not fetch available years")
    st.stop()

# State selection
states = fetch_api_data("states")
if states:
    state_options = ["All States"] + [s["state"] for s in states]
    selected_state = st.sidebar.selectbox(
        "Select State",
        state_options
    )
else:
    st.error("Could not fetch states")
    st.stop()

# Main content
st.title("Economic Agency Index Dashboard")
st.markdown("""
    The Economic Agency Index (EAI) measures the relative weight of three income streams in US counties:
    - Earned income (wages and self-employment)
    - Property income (dividends, interest, and rent)
    - Government transfers
    
    Higher EAI scores indicate stronger local economic agency, while lower scores suggest greater dependence on external sources.
""")

# Fetch data for the selected year
params = {"state": selected_state if selected_state != "All States" else None}
year_data = fetch_api_data(f"eai/year/{selected_year}", params)

if year_data:
    # Create and display the choropleth map
    st.plotly_chart(
        create_choropleth_map(year_data, selected_year),
        use_container_width=True
    )
    
    # County selection for detailed view
    counties = fetch_api_data("counties", params)
    if counties:
        county_options = {f"{c['name']}, {c['state']}": c['fips'] for c in counties}
        selected_county = st.selectbox(
            "Select County for Detailed View",
            list(county_options.keys())
        )
        
        # Fetch and display county details
        county_data = fetch_api_data(f"eai/{county_options[selected_county]}")
        if county_data:
            # Create metrics row
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Current EAI Score",
                    f"{county_data[-1]['eai_score']:.2f}",
                    f"{county_data[-1]['eai_score'] - county_data[-2]['eai_score']:.2f}"
                )
            
            with col2:
                st.metric(
                    "Earned Income Share",
                    f"{county_data[-1]['earned_share']:.1%}",
                    f"{county_data[-1]['earned_share'] - county_data[-2]['earned_share']:.1%}"
                )
            
            with col3:
                st.metric(
                    "Property Income Share",
                    f"{county_data[-1]['property_share']:.1%}",
                    f"{county_data[-1]['property_share'] - county_data[-2]['property_share']:.1%}"
                )
            
            with col4:
                st.metric(
                    "Transfer Share",
                    f"{county_data[-1]['transfer_share']:.1%}",
                    f"{county_data[-1]['transfer_share'] - county_data[-2]['transfer_share']:.1%}"
                )
            
            # Create and display time series
            st.plotly_chart(
                create_time_series(county_data, selected_county),
                use_container_width=True
            )
            
            # Download button
            if st.button("Download County Data"):
                csv_data = pd.DataFrame(county_data).to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    csv_data,
                    f"eai_{county_options[selected_county]}_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv"
                )

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center'>
        <p>Data sources: Bureau of Economic Analysis (BEA), Internal Revenue Service (IRS), US Census Bureau</p>
        <p>Last updated: {}</p>
    </div>
""".format(datetime.now().strftime("%Y-%m-%d")), unsafe_allow_html=True) 