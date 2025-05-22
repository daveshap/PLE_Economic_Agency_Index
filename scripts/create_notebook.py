import nbformat as nbf
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ipywidgets as widgets
from IPython.display import display, clear_output
import plotly.figure_factory as ff

# Create a new notebook
nb = nbf.v4.new_notebook()

# Create the cells
cells = [
    nbf.v4.new_markdown_cell("""# BEA Data Analysis

This notebook loads and analyzes the Bureau of Economic Analysis (BEA) county-level personal income data."""),

    nbf.v4.new_code_cell("""import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ipywidgets as widgets
from IPython.display import display, clear_output

# Set plot style
plt.style.use('seaborn-v0_8')
sns.set_theme()

# Display settings
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', 100)
pd.set_option('display.width', 1000)"""),

    nbf.v4.new_markdown_cell("""## Load the Data

Load the CAINC4 dataset which contains county-level personal income data."""),

    nbf.v4.new_code_cell("""# Load the data
file_path = '../data/raw/CAINC4__ALL_AREAS_1969_2023.csv'

# Try different encodings
encodings = ['latin1', 'cp1252', 'utf-8', 'utf-8-sig']
df = None

for encoding in encodings:
    try:
        df = pd.read_csv(file_path, encoding=encoding)
        print(f"Successfully read file with {encoding} encoding")
        break
    except UnicodeDecodeError:
        print(f"Failed to read with {encoding} encoding")
        continue

if df is None:
    raise ValueError("Could not read the file with any of the attempted encodings")

# Display basic information about the dataset
print("\\nDataset shape:", df.shape)
print("\\nColumns in the dataset:")
print(df.columns.tolist())
print("\\nFirst few rows of the data:")
display(df.head())"""),

    nbf.v4.new_markdown_cell("""## Data Overview

Let's examine the data types and basic statistics of the dataset."""),

    nbf.v4.new_code_cell("""# Display data types and non-null counts
print("Data types and non-null counts:")
display(df.info())

# Display basic statistics
print("\\nBasic statistics:")
display(df.describe())"""),

    nbf.v4.new_markdown_cell("""## Data Quality Check

Check for missing values and unique values in key columns."""),

    nbf.v4.new_code_cell("""# Check for missing values
print("Missing values per column:")
display(df.isnull().sum())

# Display unique values in key columns
print("\\nUnique values in key columns:")
for col in ['GeoFIPS', 'GeoName', 'LineCode']:
    if col in df.columns:
        print(f"\\n{col}:")
        print(f"Number of unique values: {df[col].nunique()}")
        print("Sample values:")
        display(df[col].unique()[:5])"""),

    nbf.v4.new_markdown_cell("""## Filter Data for Specific Line Items

Filter the data to include only line items 50 (Total personal income), 110 (Net earnings), and 240 (Per capita personal income)."""),

    nbf.v4.new_code_cell("""# Filter to specific line items
line_items = [50, 110, 240]
filtered_df = df[df['LineCode'].isin(line_items)].copy()

# Convert LineCode to string for better display
filtered_df['LineCode'] = filtered_df['LineCode'].astype(str)

# Display the filtered data
print("Filtered data shape:", filtered_df.shape)
print("\\nUnique line items in filtered data:")
print(filtered_df['LineCode'].unique())
print("\\nSample of filtered data:")
display(filtered_df.head())"""),

    nbf.v4.new_markdown_cell("""## Create Interactive Choropleth Map

Create an interactive choropleth map showing total personal income (LineCode 50) by county, with a year selector."""),

    nbf.v4.new_code_cell("""# Create Choropleth Map
import plotly.figure_factory as ff

# Create the choropleth map
fig = ff.create_choropleth(
    fips=filtered_df[filtered_df['LineCode'] == '50']['GeoFIPS'].tolist(),
    values=filtered_df[filtered_df['LineCode'] == '50']['2022'].tolist(),
    scope=['usa'],
    show_state_data=True,
    show_hover=True,
    binning_endpoints=[0, 1000000, 5000000, 10000000, 50000000, 100000000, 500000000, 1000000000],
    county_outline={'color': 'rgb(255,255,255)', 'width': 0.5},
    legend_title='Total Personal Income',
    title='Total Personal Income by County (2022)'
)

fig.update_layout(
    geo=dict(
        center=dict(lat=39.8283, lon=-98.5795),
        projection_scale=3
    ),
    margin=dict(l=0, r=0, t=30, b=0)
)

fig.show()

# Add Interactive Year Selection
# Get available years from the data
years = [col for col in filtered_df.columns if col.isdigit()]
years.sort()

# Create dropdown widget
year_dropdown = widgets.Dropdown(
    options=years,
    value=years[-1],  # Default to most recent year
    description='Select Year:',
    style={'description_width': 'initial'}
)

# Create output widget for the map
map_output = widgets.Output()

def update_map(year):
    with map_output:
        clear_output(wait=True)
        fig = ff.create_choropleth(
            fips=filtered_df[filtered_df['LineCode'] == '50']['GeoFIPS'].tolist(),
            values=filtered_df[filtered_df['LineCode'] == '50'][str(year)].tolist(),
            scope=['usa'],
            show_state_data=True,
            show_hover=True,
            binning_endpoints=[0, 1000000, 5000000, 10000000, 50000000, 100000000, 500000000, 1000000000],
            county_outline={'color': 'rgb(255,255,255)', 'width': 0.5},
            legend_title='Total Personal Income',
            title=f'Total Personal Income by County ({year})'
        )
        
        fig.update_layout(
            geo=dict(
                center=dict(lat=39.8283, lon=-98.5795),
                projection_scale=3
            ),
            margin=dict(l=0, r=0, t=30, b=0)
        )
        
        fig.show()

# Connect the dropdown to the update function
year_dropdown.observe(lambda change: update_map(change.new), names='value')

# Display widgets
display(widgets.VBox([year_dropdown, map_output]))

# Initial map display
update_map(years[-1])""")
]

# Add the cells to the notebook
nb['cells'] = cells

# Add metadata
nb['metadata'] = {
    'kernelspec': {
        'display_name': 'Python 3',
        'language': 'python',
        'name': 'python3'
    },
    'language_info': {
        'codemirror_mode': {
            'name': 'ipython',
            'version': 3
        },
        'file_extension': '.py',
        'mimetype': 'text/x-python',
        'name': 'python',
        'nbconvert_exporter': 'python',
        'pygments_lexer': 'ipython3',
        'version': '3.8.0'
    }
}

# Create notebooks directory if it doesn't exist
os.makedirs('notebooks', exist_ok=True)

# Write the notebook to a file
with open('notebooks/bea_data_analysis.ipynb', 'w', encoding='utf-8') as f:
    nbf.write(nb, f) 