"""
Streamlit dashboard for the Economic Agency Index.
"""

import streamlit as st

# Page configuration must be the first Streamlit command
st.set_page_config(
    page_title="Economic Agency Index Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from datetime import datetime
import yaml
from pathlib import Path
import altair as alt
import numpy as np
import requests
import plotly.figure_factory as ff

# Load configuration
project_root = Path(__file__).parent.parent.parent
with open(project_root / "config.yaml") as f:
    config = yaml.safe_load(f)

# Load counties GeoJSON data
@st.cache_data
def load_counties_geojson():
    """Load counties GeoJSON data."""
    url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
    response = requests.get(url)
    return response.json()

# Load counties data
counties = load_counties_geojson()

# Enhanced GeoJSON Debugging
st.write("--- GeoJSON Details (Initial Load) ---")
st.write("GeoJSON Keys:", list(counties.keys()))
if "features" in counties and isinstance(counties["features"], list) and len(counties["features"]) > 0:
    st.write("Number of features:", len(counties["features"]))
    st.write("First feature (sample):", json.dumps(counties["features"][0], indent=2))
    # Check for 'id' in the first feature
    if "id" in counties["features"][0]:
        st.write("ID of first feature:", counties["features"][0]["id"])
        # Specifically check if "01001" is an ID in any feature
        geojson_fips_ids = {feature['id'] for feature in counties['features'] if 'id' in feature}
        if "01001" in geojson_fips_ids:
            st.write("✅ Test FIPS '01001' is present as an 'id' in GeoJSON features.")
        else:
            st.error("❌ Test FIPS '01001' is NOT found as an 'id' in GeoJSON features. The test map will likely be blank.")
    else:
        st.error("❌ First feature in GeoJSON does NOT have an 'id' field. This is likely the problem.")
        st.write("   Please check the structure of the GeoJSON. It might use 'properties.FIPS' or similar for the feature identifier.")
else:
    st.error("❌ GeoJSON does not contain 'features', features list is empty, or not a list. Cannot draw map.")
st.write("--- End GeoJSON Details (Initial Load) ---")

# Extract just the feature for "01001" for a super-focused test
single_feature_geojson = None
if "features" in counties and isinstance(counties["features"], list):
    for feature in counties["features"]:
        if feature.get("id") == "01001":
            single_feature_geojson = {
                "type": "FeatureCollection",
                "features": [feature]
            }
            st.write("✅ Created a minimal GeoJSON containing only the feature for FIPS 01001.")
            break
if not single_feature_geojson:
    st.error("❌ Could not extract feature '01001' to create a minimal GeoJSON for the test map.")

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

# Load and process data
@st.cache_data
def load_data(selected_line_code):
    """Load and process BEA data."""
    # Load the data
    df = pd.read_csv(
        project_root / "data" / "raw" / "bea" / "CAINC4__ALL_AREAS_1969_2023.csv",
        encoding='latin1',
        low_memory=False  # Handle mixed types warning
    )
    
    # Get debug parameter
    debug = st.experimental_get_query_params().get("debug", ["False"])[0].lower() == "true"
    
    if debug:
        st.write("Initial data shape:", df.shape)
        st.write("Sample of initial GeoFIPS values:", df['GeoFIPS'].head(10).tolist())
        st.write("Sample of initial GeoName values:", df['GeoName'].head(10).tolist())
    
    # Filter out rows where GeoFIPS is not a valid FIPS code
    # First convert to string and clean up
    df['GeoFIPS'] = df['GeoFIPS'].astype(str).str.strip().str.replace('"', '').str.replace("'", '')
    if debug:
        st.write("Sample of cleaned GeoFIPS before filtering:", df['GeoFIPS'].head(10).tolist())
    
    # Keep only rows where GeoFIPS is a valid FIPS code (5 digits)
    df = df[df['GeoFIPS'].str.match(r'^\d{5}$', na=False)]
    if debug:
        st.write("Shape after FIPS code filter:", df.shape)
    
    # Clean and convert GeoFIPS to proper format (already 5 digits, just ensure string format)
    df["GeoFIPS"] = df["GeoFIPS"].astype(str).str.zfill(5)
    if debug:
        st.write("Sample of final GeoFIPS values:", df['GeoFIPS'].head(10).tolist())
    
    # Get year columns (columns that contain year data)
    year_columns = [col for col in df.columns if col.isdigit()]
    
    # Clean numeric columns first, before any filtering
    for year_col in year_columns:
        # First convert to string and clean up the data
        df[year_col] = df[year_col].astype(str)
        # Remove any asterisks
        df[year_col] = df[year_col].str.replace('*', '', regex=False)
        # Replace (NA) with NaN
        df[year_col] = df[year_col].str.replace('(NA)', 'NaN', regex=False)
        # Remove any commas
        df[year_col] = df[year_col].str.replace(',', '', regex=False)
        # Convert to numeric, coercing errors to NaN
        df[year_col] = pd.to_numeric(df[year_col], errors='coerce')
    
    # Get US total data (for metrics)
    us_total_data = df[df['GeoName'] == 'United States']
    if debug:
        st.write("Number of US total rows:", len(us_total_data))
    us_total_data = us_total_data[us_total_data['LineCode'] == selected_line_code]
    if debug:
        st.write("Number of US total rows after LineCode filter:", len(us_total_data))
    
    # Filter for county data (keep only entries with comma + state abbreviation)
    # First get all rows that are not "United States"
    county_data = df[df['GeoName'] != 'United States']
    if debug:
        st.write("Number of rows after removing US total:", len(county_data))
    
    # Remove any entries with asterisks in the name
    county_data = county_data[~county_data['GeoName'].str.contains('*', regex=False, na=False)]
    if debug:
        st.write("Number of rows after removing asterisks:", len(county_data))
    
    # Define state abbreviations
    state_abbrs = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 
                   'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 
                   'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 
                   'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 
                   'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']
    
    # Create a pattern to match entries that end with ", XX" where XX is a state abbreviation
    state_pattern = '|'.join([f', {abbr}$' for abbr in state_abbrs])
    county_data = county_data[county_data['GeoName'].str.contains(state_pattern, regex=True, na=False)]
    if debug:
        st.write("Number of rows after state pattern filter:", len(county_data))
        st.write("Sample of county names after filtering:", county_data['GeoName'].head(10).tolist())
    
    # Extract county name (everything before the comma)
    county_data['CountyName'] = county_data['GeoName'].str.split(',').str[0]
    
    # Filter for selected LineCode
    county_data = county_data[county_data['LineCode'] == selected_line_code]
    if debug:
        st.write("Number of rows after LineCode filter:", len(county_data))
        st.write("Number of counties found:", len(county_data))
        st.write("Top 10 county names:", county_data['CountyName'].head(10).tolist())
    
    # Get unique states (extract state abbreviations from county names)
    states = sorted(county_data['GeoName'].str.extract(f', ({state_pattern})')[0].unique())
    if debug:
        st.write("Found states:", states)
    
    return county_data, us_total_data, year_columns, states

# Sidebar
st.sidebar.title("Economic Agency Index Dashboard")
st.sidebar.markdown("---")

# LineCode selection
line_code_options = [50, 110, 240]
selected_line_code = st.sidebar.selectbox(
    "Select Income Component",
    line_code_options,
    index=0,
    format_func=lambda x: {
        50: "Wages and Salaries",
        110: "Personal Income",
        240: "Disposable Personal Income"
    }[x]
)

# Load the data with selected LineCode
try:
    county_data, us_total_data, year_columns, states = load_data(selected_line_code)
    
    if len(county_data) == 0:
        st.error("No county data found after filtering. Please check the data file and filters.")
        st.stop()
        
    if not year_columns:
        st.error("No year columns found in the data. Please check the data file format.")
        st.stop()
        
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.info("Please ensure the BEA data file is available at data/raw/bea/CAINC4__ALL_AREAS_1969_2023.csv")
    st.stop()

# Year selection
selected_year = st.sidebar.selectbox(
    "Select Year",
    sorted(year_columns, reverse=True),
    index=0
)

# State selection
state_options = ["All States"] + list(states)
selected_state = st.sidebar.selectbox(
    "Select State",
    state_options
)

# Main content
st.title("Economic Agency Index Dashboard")
st.markdown("""
    The Economic Agency Index (EAI) measures the relative weight of three income streams in US counties:
    - Earned income (wages and self-employment)
    - Property income (dividends, interest, and rent)
    - Government transfers
    
    Higher EAI scores indicate stronger local economic agency, while lower scores suggest greater dependence on external sources.
""")

# Filter data based on selection
filtered_data = county_data.copy()
debug = st.experimental_get_query_params().get("debug", ["False"])[0].lower() == "true"

if debug:
    st.write("Total rows in county_data:", len(county_data))
    st.write("Top 10 GeoFIPS (from county_data):", county_data['GeoFIPS'].head(10).tolist())
    st.write("Top 10 County Names (from county_data):", county_data['CountyName'].head(10).tolist())
    st.write(f"Top 10 values for {selected_year} (from county_data):", county_data[selected_year].head(10).tolist())

if selected_state != "All States":
    filtered_data = filtered_data[filtered_data['GeoName'].str.contains(f', {selected_state}$', regex=True)]
    if debug:
        st.write("Rows after state filter:", len(filtered_data))

# Ensure the data for coloring is numeric and handle potential issues
color_col_name = 'color_value'
log_color_col_name = 'log_color_value' # New column for log transformed data

if selected_year in filtered_data.columns:
    filtered_data[color_col_name] = pd.to_numeric(filtered_data[selected_year], errors='coerce')
    # Apply log transformation - ensure values are positive
    if not filtered_data[color_col_name].empty and (filtered_data[color_col_name] > 0).all():
        filtered_data[log_color_col_name] = np.log(filtered_data[color_col_name])
    else:
        # Handle cases with non-positive values or empty series if necessary, or let it be NaN
        filtered_data[log_color_col_name] = pd.Series(dtype='float64', index=filtered_data.index) # Ensure index alignment
else:
    filtered_data[color_col_name] = pd.Series(dtype='float64')
    filtered_data[log_color_col_name] = pd.Series(dtype='float64')


# Debugging the color column
if debug: # Combined debug block
    st.write(f"--- Debugging '{color_col_name}' and '{log_color_col_name}' columns ---")
    st.write(f"Data type of '{color_col_name}':", filtered_data[color_col_name].dtype)
    st.write(f"Number of NaNs in '{color_col_name}':", filtered_data[color_col_name].isna().sum())
    if not filtered_data[color_col_name].isna().all():
        st.write(f"Min value in '{color_col_name}':", filtered_data[color_col_name].min())
        st.write(f"Max value in '{color_col_name}':", filtered_data[color_col_name].max())
        st.write(f"Sample values from '{color_col_name}': {filtered_data[color_col_name].dropna().head().tolist()}")
    else:
        st.write(f"All values in '{color_col_name}' are NaN.")

    if log_color_col_name in filtered_data.columns:
        st.write(f"Data type of '{log_color_col_name}':", filtered_data[log_color_col_name].dtype)
        st.write(f"Number of NaNs in '{log_color_col_name}':", filtered_data[log_color_col_name].isna().sum())
        st.write(f"Number of infinite values in '{log_color_col_name}':", np.isinf(filtered_data[log_color_col_name]).sum()) # Check for inf
        if not filtered_data[log_color_col_name].isna().all() and not np.isinf(filtered_data[log_color_col_name]).any():
            st.write(f"Min value in '{log_color_col_name}':", filtered_data[log_color_col_name].min())
            st.write(f"Max value in '{log_color_col_name}':", filtered_data[log_color_col_name].max())
            st.write(f"Sample values from '{log_color_col_name}': {filtered_data[log_color_col_name].dropna().head().tolist()}")
        else:
            st.write(f"All values in '{log_color_col_name}' are NaN, infinite, or column not generated properly.")
    st.write("--- End Debugging ---")


# Verify we have data before proceeding
if len(filtered_data) == 0:
    st.error(f"No data found for state: {selected_state}")
    st.stop()

# Verify the selected year column exists and has data for coloring
if log_color_col_name not in filtered_data.columns or filtered_data[log_color_col_name].isna().all() or np.isinf(filtered_data[log_color_col_name]).any(): # Check log column for NaNs or inf
    st.error(f"No valid (non-NaN, finite) log-transformed data available for year {selected_year} (column '{log_color_col_name}') to color the map after filtering.")
    st.stop()

if debug:
    st.write("--- Data going into main choropleth map (head) ---")
    st.write(filtered_data[["GeoFIPS", "CountyName", log_color_col_name]].head())
    st.write(f"Shape of filtered_data: {filtered_data.shape}")
    st.write(f"Number of unique GeoFIPS in filtered_data for map: {filtered_data['GeoFIPS'].nunique()}")

    st.write("--- GeoJSON Details (Before Plotting Main Map) ---")
    st.write("Number of features in 'counties' GeoJSON:", len(counties.get("features", [])) if isinstance(counties.get("features"), list) else "N/A or not a list")
    if "features" in counties and isinstance(counties["features"], list) and len(counties["features"]) > 0 and "id" in counties["features"][0]:
         st.write("Sample feature ID from 'counties' GeoJSON:", counties["features"][0]["id"])
    else:
        st.write("Sample feature ID from 'counties' GeoJSON: Not available or 'id' field missing.")
    st.write("--- End GeoJSON Details (Before Plotting Main Map) ---")


geo_ids = {feat["id"] for feat in counties.get("features", []) if isinstance(counties.get("features"), list) and "id" in feat} # Defensive
df_ids  = set(filtered_data["GeoFIPS"])
matches    = geo_ids & df_ids
mismatches = df_ids - geo_ids

st.write(f"✅ matched counties between GeoJSON and data: {len(matches)}")
st.write(f"❌ GeoFIPS in data but not in GeoJSON (first 10): {list(mismatches)[:10]}")
if not matches and len(df_ids) > 0:
    st.warning("No FIPS codes in your data match the FIPS codes in the GeoJSON. The map will likely be blank.")


# Create choropleth map using go.Choropleth based on minimal_plotly_test.py learnings
fig = go.Figure(data=[go.Choropleth(
    geojson=counties,
    locations=filtered_data["GeoFIPS"].tolist(),
    z=filtered_data[log_color_col_name].tolist(),
    featureidkey="id",
    colorscale="Plasma",
    hovertext=filtered_data["CountyName"].tolist(), # For hover info
    # marker_line_color='darkgray', # Optional: can add if desired
    # marker_line_width=0.5       # Optional: can add if desired
)])

fig.update_layout(
    title_text=f"{'Wages and Salaries' if selected_line_code == 50 else 'Personal Income' if selected_line_code == 110 else 'Disposable Personal Income'} by County (Log Scale) — {selected_year}",
    geo=dict(
        scope="usa",
        projection_type="albers usa", # Consistent with working examples
        # showlakes=True, # Add back cautiously
        # lakecolor="white", # Add back cautiously
        # showsubunits=True, # Add back cautiously
        # subunitcolor="lightgray" # Add back cautiously
    ),
    margin=dict(r=0, t=30, l=0, b=0),
    height=600,
    # labels are implicitly handled by hovertext and colorscale legend for go.Choropleth
    # If specific legend title for color bar is needed, it's usually within colorscale settings or annotations.
    # For now, the main title and hovertext should provide context.
)

# Display the map
st.plotly_chart(fig, use_container_width=True)

st.write("--- Single County Test Map (ULTRA-SIMPLE go.Choropleth) ---")
st.write("Attempting to render county 01001 with value 1. Check if ANY map area appears.")
# test_df = pd.DataFrame({"GeoFIPS": ["01001"], "val": [1]}) # Not using test_df for this version

if single_feature_geojson: # Only attempt if we successfully created the minimal GeoJSON
    simple_test_fig = go.Figure(data=[
        go.Choropleth(
            locations=["01001"],             # Hardcoded list with one FIPS
            z=[1.0],                       # Hardcoded list with one float value
            geojson=single_feature_geojson,  # Minimal GeoJSON with only feature 01001
            featureidkey="id",
            colorscale="Reds",
        )
    ])
    
    # NO LAYOUT UPDATES AT ALL - PURE DEFAULTS
    simple_test_fig.update_layout(title_text='Ultra-Simple Test Map (01001 only)', height=300) # Minimal layout

    st.write("Attempting to render ultra-simple go.Choropleth fig:", simple_test_fig is not None)
    try:
        st.plotly_chart(simple_test_fig, use_container_width=True)
        st.write("st.plotly_chart for ultra-simple map executed without Python error.")
    except Exception as e:
        st.error(f"Python error during st.plotly_chart for ultra-simple map: {e}")
else:
    st.error("Cannot render the ultra-simple single county test map because the minimal GeoJSON for it is missing.")


# Debug information after the map
if debug:
    st.write("---")
    st.write("Debug Information:")
    st.write("Number of rows:", len(filtered_data))
    st.write("Top 10 FIPS codes:", filtered_data['GeoFIPS'].head(10).tolist())
    st.write("Top 10 values:", filtered_data[selected_year].head(10).tolist())
    st.write("Min value:", filtered_data[selected_year].min())
    st.write("Max value:", filtered_data[selected_year].max())
    st.write("Number of counties:", len(filtered_data['CountyName'].unique()))
    st.write("Sample of county names:", filtered_data['CountyName'].head(10).tolist())

# Display metrics only if we have valid data
if not filtered_data[selected_year].isna().all():
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Use US total from us_total_data
        us_total = us_total_data[selected_year].iloc[0] if len(us_total_data) > 0 else 0
        prev_year = str(int(selected_year)-1)
        prev_us_total = us_total_data[prev_year].iloc[0] if len(us_total_data) > 0 and prev_year in us_total_data.columns else None
        st.metric(
            "Total US Amount",
            f"${us_total:,.0f}M",
            f"${us_total - prev_us_total:,.0f}M" if prev_us_total is not None else None
        )

    with col2:
        avg_amount = filtered_data[selected_year].mean()
        prev_avg = filtered_data[prev_year].mean() if prev_year in filtered_data.columns else None
        st.metric(
            "Average State Amount",
            f"${avg_amount:,.0f}M",
            f"${avg_amount - prev_avg:,.0f}M" if prev_avg is not None else None
        )

    with col3:
        max_idx = filtered_data[selected_year].idxmax()
        if pd.notna(max_idx):
            max_state = filtered_data.loc[max_idx, 'CountyName']
            max_value = filtered_data.loc[max_idx, selected_year]
            st.metric(
                "Highest Amount",
                max_state,
                f"${max_value:,.0f}M"
            )

    with col4:
        min_idx = filtered_data[selected_year].idxmin()
        if pd.notna(min_idx):
            min_state = filtered_data.loc[min_idx, 'CountyName']
            min_value = filtered_data.loc[min_idx, selected_year]
            st.metric(
                "Lowest Amount",
                min_state,
                f"${min_value:,.0f}M"
            )

# Display raw data
if st.checkbox("Show Raw Data"):
    st.dataframe(filtered_data)

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center'>
        <p>Data source: Bureau of Economic Analysis (BEA)</p>
        <p>Last updated: {}</p>
    </div>
""".format(datetime.now().strftime("%Y-%m-%d")), unsafe_allow_html=True)