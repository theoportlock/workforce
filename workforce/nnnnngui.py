from dash import Dash, html, dcc, Input, Output, State, ctx
import dash_cytoscape as cyto
import datetime
import io
import base64
import networkx as nx
from networkx.readwrite import json_graph
import webbrowser
import subprocess

# Initialize the Dash app
def gui(pipeline_file=None):
    app = Dash(__name__)
    app.title = "Workforce"
    app.layout = create_layout()
    register_callbacks(app)

    if pipeline_file:
        app.layout['cytoscape-elements'].elements = load(pipeline_file)

    webbrowser.open_new('http://127.0.0.1:8050/')
    app.run_server(debug=False, use_reloader=False)

# Define the layout
def create_layout():
    return html.Div([
        dcc.Store(id='last-dblclicked-node', data=None),
        html.Div([
            dcc.Upload(html.Button('Load'), id='upload-data'),
            html.Button('Save', id='btn-download'),
            dcc.Download(id='download-data'),
            html.Button('Remove', id='btn-remove', n_clicks=0),
            html.Button('Run', id='btn-runproc', n_clicks=0),
            html.Button('Update', id='btn-update', n_clicks=0),
            html.Button('Clear', id='btn-clear', n_clicks=0),
        ], style={'display': 'flex', 'gap': '2px'}),
        
        html.Div([
            dcc.Input(
                id='txt_node', value='echo "Input bash command"', type='text',
                style={'width': '400px', 'margin-right': '2px'}
            ),
            html.Button('+', id='btn-add', n_clicks=0, 
                        style={'background-color': 'lightgreen'})
        ], style={'margin-top': '2px'}),

        html.Hr(),
        cyto.Cytoscape(
            id='cytoscape-elements',
            layout={'name': 'preset', 'directed': True},
            style={'width': '100%', 'height': '85vh'},
            stylesheet=create_stylesheet(),
            autoRefreshLayout=False,
            elements=[],
            zoomingEnabled=True,
            userZoomingEnabled=True,
            wheelSensitivity=0.1,
        ),
        html.Hr(),
        'workforce: ' + str(datetime.datetime.now()),
    ])

# Define styles for nodes and edges
def create_stylesheet():
    return [
        {'selector': 'node', 'style': {
            'label': 'data(label)',
            'font-size': '10px',
            'width': '30px',
            'height': '30px',
            'text-wrap': 'wrap',
            'background-color': 'lightgray'}},
        {'selector': 'node:selected', 'style': {'background-color': 'gray'}},
        {'selector': 'edge', 'style': {
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'line-color': 'lightgray',
            'target-arrow-color': 'lightgray'}},
        {'selector': 'edge:selected', 'style': {
            'line-color': 'gray',
            'target-arrow-color': 'gray'}}
    ]

# Register Dash callbacks
def register_callbacks(app):
    @app.callback(
        Output('last-dblclicked-node', 'data'),
        Input('cytoscape-elements', 'dblTapNodeData'),
        prevent_initial_call=True
    )
    def store_dblclicked_node(dbl_tap_node_data):
        return dbl_tap_node_data['id'] if dbl_tap_node_data else None

    @app.callback(
        Output('cytoscape-elements', 'elements'),
        Input('cytoscape-elements', 'tapNodeData'),
        State('last-dblclicked-node', 'data'),
        State('cytoscape-elements', 'elements'),
        prevent_initial_call=True
    )
    def connect_nodes_on_click(tap_node_data, last_dblclicked_node, elements):
        if last_dblclicked_node and tap_node_data and tap_node_data['id'] != last_dblclicked_node:
            elements.append({'data': {
                'source': last_dblclicked_node,
                'target': tap_node_data['id'],
                'id': f"{last_dblclicked_node}-{tap_node_data['id']}"}})
        return elements

# Load elements from a GraphML file
def load(pipeline_file):
    G = nx.read_graphml(pipeline_file)
    elements = json_graph.node_link_data(G)['nodes'] + json_graph.node_link_data(G)['links']
    return [{'data': e['data']} for e in elements]

# Run the GUI
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("pipeline", nargs='?')
    args = parser.parse_args()
    gui(args.pipeline) if args.pipeline else gui()

if __name__ == '__main__':
    main()

