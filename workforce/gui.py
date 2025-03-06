#!/usr/bin/env python3
from dash import Dash, html, Input, Output, State, dcc, ctx
import argparse
import base64
import dash
import dash_cytoscape as cyto
import datetime
import io
import networkx as nx
import subprocess
import sys
import webbrowser

def Gui(pipeline_file=None):
    # Initialize with empty elements and pipeline preview
    initial_elements = []
    initial_pipeline = ""
    initial_pipeline_file = None

    if pipeline_file:
        # Load graph elements from the file
        initial_elements = load(pipeline_file)
        try:
            with open(pipeline_file, 'r') as f:
                content = f.read()
            preview = content[:500] + ('...' if len(content) > 500 else '')
            initial_pipeline = f"Pipeline File: {pipeline_file}\n\n{preview}"
        except Exception as e:
            initial_pipeline = f"Error reading {pipeline_file}: {e}"
        initial_pipeline_file = pipeline_file

    app = Dash(__name__)
    app.title = "Workforce"
    app.layout = create_layout(initial_elements, initial_pipeline, initial_pipeline_file)
    register_callbacks(app)
    webbrowser.open_new('http://127.0.0.1:8050/')
    app.run_server(debug=False, use_reloader=False)

def create_layout(initial_elements, initial_pipeline, initial_pipeline_file):
    return html.Div([
        # Top controls
        html.Div([
            dcc.Upload(html.Button('Load'), id='upload-data'),
            html.Button('Save', id='btn-download'),
            dcc.Download(id='download-data'),
            html.Button('Remove', id='btn-remove', n_clicks=0),
            html.Button('Run', id='btn-runproc', n_clicks=0),
            html.Button('Connect', id='btn-connect', n_clicks=0),
            html.Button('Update', id='btn-update', n_clicks=0),
            html.Button('Clear', id='btn-clear', n_clicks=0),
            html.Button('View Pipeline', id='btn-view-pipeline', n_clicks=0),
            html.Button('Run Pipeline', id='btn-run-pipeline', n_clicks=0),
            # Store the current pipeline filename
            dcc.Store(id='pipeline-file-store', data=initial_pipeline_file)
        ], style={'display': 'flex', 'flex-direction': 'row', 'gap': '2px'}),

        # Node text input and add button
        html.Div([
            dcc.Input(
                id='txt_node',
                value='echo "Input bash command"',
                type='text',
                style={'width': '400px', 'margin-right': '2px'}
            ),
            html.Button('+', id='btn-add', n_clicks=0,
                        style={'margin-right': '2px', 'background-color': 'lightgreen'})
        ], style={'margin-top': '2px'}),

        html.Hr(),

        # Cytoscape graph area
        cyto.Cytoscape(
            id='cytoscape-elements',
            layout={'name': 'preset', 'directed': True},
            style={'width': '100%', 'height': '85vh'},
            stylesheet=create_stylesheet(),
            elements=initial_elements,
            autoRefreshLayout=False,
            responsive=True,
            zoomingEnabled=True,
            userZoomingEnabled=True,
            wheelSensitivity=0.1,
        ),

        html.Hr(),

        # Pipeline file display area
        html.Div(id='pipeline-output',
                 children=initial_pipeline,
                 style={'margin-top': '20px', 'white-space': 'pre-wrap'}),

        # Footer with timestamp
        html.Div('workforce: ' + str(datetime.datetime.now()))
    ])

def create_stylesheet():
    return [
        {
            'selector': 'node',
            'style': {
                'label': 'data(label)',
                'font-size': '10px',
                'width': '30px',
                'height': '30px',
                'text-max-width': '150px',
                'text-wrap': 'wrap',
                'background-color': 'lightgray',
            },
        },
        {
            'selector': 'node:selected',
            'style': {
                'background-color': 'gray',
            },
        },
        {
            'selector': 'edge',
            'style': {
                'curve-style': 'bezier',
                'target-arrow-shape': 'triangle',
                'line-color': 'lightgray',
                'target-arrow-color': 'lightgray',
            },
        },
        {
            'selector': 'edge:selected',
            'style': {
                'line-color': 'gray',
                'target-arrow-color': 'gray',
            },
        },
    ]

def register_callbacks(app):
    # Callback for updating the network elements and processing file uploads
    @app.callback(
        Output('cytoscape-elements', 'elements'),
        [Input('upload-data', 'contents'),
         Input('btn-add', 'n_clicks'),
         Input('btn-remove', 'n_clicks'),
         Input('btn-connect', 'n_clicks'),
         Input('btn-update', 'n_clicks')],
        [State('txt_node', 'value'),
         State('upload-data', 'filename'),
         State('cytoscape-elements', 'elements'),
         State("cytoscape-elements", "selectedNodeData"),
         State("cytoscape-elements", "selectedEdgeData")],
        prevent_initial_call=True
    )
    def modify_network(contents, add_clicks, remove_clicks, connect_clicks, update_clicks,
                       txt_node, filename, elements, selected_nodes, selected_edges):
        if ctx.triggered_id == 'upload-data' and contents is not None:
            elements = handle_upload(contents)
        elif ctx.triggered_id == 'btn-add':
            elements = add_node(elements, txt_node)
        elif ctx.triggered_id == 'btn-remove':
            elements = remove(elements, selected_nodes, selected_edges)
        elif ctx.triggered_id == 'btn-connect':
            elements = connect_nodes(elements, selected_nodes)
        elif ctx.triggered_id == 'btn-update':
            elements = update_node(elements, selected_nodes, txt_node)
        return elements

    # Callback for updating the pipeline file display and store when a new file is uploaded
    @app.callback(
        [Output('pipeline-output', 'children'),
         Output('pipeline-file-store', 'data')],
        [Input('upload-data', 'contents')],
        [State('upload-data', 'filename')],
        prevent_initial_call=True
    )
    def update_pipeline_upload(contents, filename):
        if contents and filename:
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string).decode('utf-8')
            preview = decoded[:500] + ('...' if len(decoded) > 500 else '')
            return f"Pipeline File: {filename}\n\n{preview}", filename
        raise dash.exceptions.PreventUpdate

    @app.callback(
        Output('download-data', 'data'),
        [Input('btn-download', 'n_clicks')],
        [State('cytoscape-elements', 'elements')],
        prevent_initial_call=True
    )
    def save_data(n_clicks, elements):
        return save_elements(elements)

    @app.callback(
        Output('btn-runproc', 'n_clicks'),
        [Input('btn-runproc', 'n_clicks')],
        [State('cytoscape-elements', 'selectedNodeData')],
        prevent_initial_call=True
    )
    def run_process(n_clicks, data):
        execute_process(data)
        return 0

    @app.callback(
        Output('txt_node', 'value'),
        [Input('cytoscape-elements', 'tapNodeData'),
         Input('btn-clear', 'n_clicks')],
        prevent_initial_call=True
    )
    def update_text_box(tap_node_data, n_clicks):
        if ctx.triggered_id == 'cytoscape-elements' and tap_node_data is not None:
            return tap_node_data['label']
        elif ctx.triggered_id == 'btn-clear':
            return ''
        return dash.no_update

    @app.callback(
        Output('btn-view-pipeline', 'n_clicks'),
        [Input('btn-view-pipeline', 'n_clicks')],
        [State('pipeline-file-store', 'data')],
        prevent_initial_call=True
    )
    def view_pipeline(n_clicks, filename):
        if filename:
            subprocess.run([sys.executable, "-m", "workforce", "view", filename])
        return 0

    @app.callback(
        Output('btn-run-pipeline', 'n_clicks'),
        [Input('btn-run-pipeline', 'n_clicks')],
        [State('pipeline-file-store', 'data')],
        prevent_initial_call=True
    )
    def run_pipeline(n_clicks, filename):
        if filename:
            subprocess.run([sys.executable, "-m", "workforce", "run", filename])
        return 0

def handle_upload(contents):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    return load(io.BytesIO(decoded))

def load(pipeline_file):
    # Read GraphML and convert it to dash-cytoscape elements using networkx
    G = nx.read_graphml(pipeline_file)
    graph = nx.readwrite.json_graph.node_link_data(G)
    elements = graph['nodes'] + graph['links']
    dash_elements = []
    for element in elements:
        if 'source' in element and 'target' in element:
            dash_elements.append({
                'data': {
                    'source': element.get('source'),
                    'target': element.get('target'),
                    'id': element.get('id')
                }
            })
        else:
            dash_elements.append({
                'data': {
                    'label': element.get('label'),
                    'id': element.get('id')
                },
                'position': {
                    'x': float(element.get('x', 0)),
                    'y': float(element.get('y', 0))
                }
            })
    return dash_elements

def add_node(elements, txt_node):
    elements.append({'data': {'label': txt_node}})
    return elements

def remove(elements, selected_nodes, selected_edges):
    selected_node_labels = {node['label'] for node in selected_nodes} if selected_nodes else set()
    selected_edge_pairs = {(edge['source'], edge['target']) for edge in selected_edges} if selected_edges else set()
    return [
        el for el in elements
        if el['data'].get('label') not in selected_node_labels and
           (el['data'].get('source'), el['data'].get('target')) not in selected_edge_pairs
    ]

def connect_nodes(elements, selected_nodes):
    if not selected_nodes or len(selected_nodes) < 2:
        return elements
    for i in range(len(selected_nodes) - 1):
        source = selected_nodes[i]['id']
        target = selected_nodes[i+1]['id']
        elements.append({'data': {'source': source, 'target': target}})
    return elements

def update_node(elements, selected_nodes, txt_node_value):
    if selected_nodes and len(selected_nodes) == 1:
        selected_id = selected_nodes[0]['id']
        for element in elements:
            if element['data'].get('id') == selected_id:
                element['data']['label'] = txt_node_value
                break
    return elements

def save_elements(elements):
    G = nx.DiGraph()
    for element in elements:
        data = element['data']
        if 'source' in data and 'target' in data:
            G.add_edge(data['source'], data['target'], id=data.get('id'))
        else:
            node_id = data.get('id')
            label = data.get('label', node_id)
            pos = element.get('position', {})
            G.add_node(node_id, label=label, x=pos.get('x', 0), y=pos.get('y', 0))
    graphml_bytes = io.BytesIO()
    nx.write_graphml(G, graphml_bytes)
    graphml_bytes.seek(0)
    return dcc.send_string(graphml_bytes.getvalue().decode('utf-8'), 'network_data.graphml')

def execute_process(data):
    if data:
        for process in data:
            subprocess.call(process['label'], shell=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="workforce",
        description="Manage and run graph-based workflows."
    )
    parser.add_argument("filename", nargs="?", help="Optional GraphML file to load")
    args = parser.parse_args()
    Gui(args.filename)

