import sqlite3
import pandas as pd
import dash
from dash import html, dcc, Input, Output, State, ctx
import plotly.graph_objects as go
import plotly.io as pio
import urllib.parse
import os

# Create the Dash app
app = dash.Dash(__name__)

# Connect to SQLite database and load data
db_path = os.getenv("HOME") + '/.config/luced/database.sqlite'  # Replace with your database path
conn = sqlite3.connect(db_path)

# Load `disk_metrics` data
query = """
SELECT timestamp, available_space_gb, used_space_gb, key 
FROM disk_metrics
"""
disk_df = pd.read_sql_query(query, conn)

# Load `cpu_metrics` data
cpu_query = """
SELECT used_percent, timestamp
FROM cpu_metrics
"""
cpu_df = pd.read_sql_query(cpu_query, conn)

# Load `cpu_metrics` data
memory_query = """
SELECT used_percent, used_gb, timestamp
FROM memory_metrics
"""
memory_df = pd.read_sql_query(memory_query, conn)

conn.close()

# Convert timestamps to datetime
disk_df['timestamp'] = pd.to_datetime(disk_df['timestamp'])
cpu_df['timestamp'] = pd.to_datetime(cpu_df['timestamp'])
memory_df['timestamp'] = pd.to_datetime(memory_df['timestamp'])



# Helper to get theme from query parameters
def get_theme_from_query(params):
    theme = params.get("theme", ["light"])[0]
    return theme if theme in ["light", "dark"] else "light"

# Layout with Theme Applied
def get_layout(theme):
    # Background color based on theme
    bg_color = "#121212" if theme == "dark" else "#ffffff"
    text_color = "#ffffff" if theme == "dark" else "#000000"

    return html.Div(
        id="app-container",
        className=theme,
        style={"backgroundColor": bg_color, "color": text_color, "minHeight": "100vh", "padding": "20px", "margin": "0"},
        children=[
            dcc.Location(id="url", refresh=True),

            html.H1("SQLite Data Visualization", style={"text-align": "center"}),

            # Theme toggle
            html.Div(
                [
                    html.Label("Select Theme:"),
                    dcc.RadioItems(
                        id="theme-toggle",
                        options=[
                            {"label": "Light Mode", "value": "light"},
                            {"label": "Dark Mode", "value": "dark"},
                        ],
                        value=theme,
                        inline=True,
                        style={"margin-bottom": "20px"},
                    ),
                ],
                style={"text-align": "center"},
            ),

            # Dropdown to select the table
            html.Label("Select a table:"),
            dcc.Dropdown(
                id="table-dropdown",
                options=[
                    {'label': html.Span(['Disk Metrics'], style={"color": "#000000"}), 'value': 'disk'},
                    {'label': html.Span(['CPU Metrics'], style={"color": "#000000"}), 'value': 'cpu'},
                    {'label': html.Span(['Memory Metrics'], style={"color": "#000000"}), 'value': 'memory'},
                ],
                value="disk",  # Default table
                multi=False,
                style={"width": "50%"},
            ),

            # Disk Metrics Controls
            html.Div(
                id="disk-controls",
                children=[
                    html.Label("Select a column to visualize:"),
                    dcc.Dropdown(
                        id="disk-column-dropdown",
                        options=[
                            {"label": html.Span(["Available Disk Size (GB)"], style={"color": "#000000"}), "value": "available_space_gb"},
                            {"label": html.Span(["Used Disk Size (GB)"], style={"color": "#000000"}), "value": "used_space_gb"},
                        ],
                        value="available_space_gb",  # Default column
                        multi=False,
                        style={"width": "50%"},
                    ),
                    html.Label("Select a device (key):"),
                    dcc.Dropdown(
                        id="disk-device-dropdown",
                        options=[{"label": html.Span([key], style={"color": "#000000"}), "value": key} for key in disk_df["key"].unique()],
                        value=disk_df["key"].unique()[0],  # Default device
                        multi=False,
                        style={"width": "50%"},
                    ),
                ],
            ),

            # CPU Metrics Controls
            html.Div(id='cpu-controls', children=[
                html.Label("CPU Usage (%):"),
                dcc.Dropdown(
                    id='cpu-column-dropdown',
                    options=[
                        {'label': html.Span(['Used Percent'], style={"color": "#000000"}), 'value': 'used_percent'}
                    ],
                    value='used_percent',  # Default column
                    multi=False,
                    style={'width': '50%'}
                ),
            ], style={'display': 'none'}),  # Initially hidden
            
            # memory Metrics Controls
            html.Div(id='memory-controls', children=[
                html.Label("Memory Usage:"),
                dcc.Dropdown(
                    id='memory-column-dropdown',
                    options=[
                        {'label': html.Span(['Used GB'], style={"color": "#000000"}), 'value': 'used_gb'},
                        {'label': html.Span(['Used Percent'], style={"color": "#000000"}), 'value': 'used_percent'}
                    ],
                    value='used_gb',  # Default column
                    multi=False,
                    style={'width': '50%'}
                ),
            ], style={'display': 'none'}),  # Initially hidden

            # Graph to display data
            dcc.Graph(id="data-visualization-graph"),
        ],
    )

# Extract theme from query string on page load
@app.callback(Output("theme-toggle", "value"), Input("url", "search"))
def apply_theme(search):
    params = urllib.parse.parse_qs(search.lstrip("?"))
    return get_theme_from_query(params)

# Trigger a page reload on theme change
@app.callback(
    Output("url", "href"),
    Output("app-container", "className"),
    Input("theme-toggle", "value"),
    State("url", "href"),
)
def reload_with_theme(theme, href):
    base_url, _, query = href.partition("?")
    params = urllib.parse.parse_qs(query)
    params["theme"] = theme
    new_query = urllib.parse.urlencode(params, doseq=True)
    # Set the theme
    if theme == 'dark':
        pio.templates.default = "plotly_dark"
    else:
        pio.templates.default = "plotly"
    app.layout = get_layout(theme)
    return f"{base_url}?{new_query}", theme

# Callbacks for table-specific controls visibility
@app.callback(
    [Output('disk-controls', 'style'), Output('cpu-controls', 'style'), Output('memory-controls', 'style')],
    [Input('table-dropdown', 'value')]
)
def toggle_controls(selected_table):
    if selected_table == 'disk':
        return {'display': 'block'}, {'display': 'none'}, {'display': 'none'}
    elif selected_table == 'cpu':
        return {'display': 'none'}, {'display': 'block'}, {'display': 'none'}
    elif selected_table == 'memory':
        return {'display': 'none'}, {'display': 'none'}, {'display': 'block'}

# Callback to update the graph based on table selection
@app.callback(
    Output('data-visualization-graph', 'config'),
    Output('data-visualization-graph', 'figure'),
    [Input('table-dropdown', 'value'),
     Input('disk-column-dropdown', 'value'),
     Input('disk-device-dropdown', 'value'),
     Input('cpu-column-dropdown', 'value'),
     Input('memory-column-dropdown', 'value')
    ],
)
def update_graph(selected_table, disk_column, disk_device, cpu_column, memory_column):
    if selected_table == 'disk':
        # Filter data for the selected device
        device_data = disk_df[disk_df['key'] == disk_device]
        
        # Create the disk metrics plot
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=device_data['timestamp'],
                y=device_data[disk_column],
                mode='lines+markers',
                name=disk_column,
                line=dict(color='blue')
            )
        )
        fig.update_layout(
            title=f"{disk_column.replace('_', ' ').title()} Over Time for {disk_device}",
            xaxis_title="Timestamp",
            yaxis_title="Value",
            hovermode="x unified"
        )
    elif selected_table == 'cpu':
        # Create the CPU metrics plot
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=cpu_df['timestamp'],
                y=cpu_df[cpu_column],
                mode='lines+markers',
                name=cpu_column,
                line=dict(color='orange')
            )
        )
        fig.update_layout(
            title=f"{cpu_column.replace('_', ' ').title()} Over Time",
            xaxis_title="Timestamp",
            yaxis_title="Value",
            hovermode="x unified"
        )
    elif selected_table == 'memory':
        # Create the CPU metrics plot
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=memory_df['timestamp'],
                y=memory_df[memory_column],
                mode='lines+markers',
                name=memory_column,
                line=dict(color='green')
            )
        )
        fig.update_layout(
            title=f"{memory_column.replace('_', ' ').title()} Over Time",
            xaxis_title="Timestamp",
            yaxis_title="Value",
            hovermode="x unified"
        )
    
    return {"scrollZoom": True}, fig

# Run the app
if __name__ == '__main__':
    pio.templates.default = "plotly"
    app.layout = get_layout("light")
    app.run_server(debug=True)
