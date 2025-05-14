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
        initial_elements, prefix, suffix = load(pipeline_file)
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
    app.run(debug=False, use_reloader=False)

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
            dcc.Input(
                id='txt_prefix',
                placeholder='prefix flags',
                type='text',
                style={'width': '100px', 'margin-right': '2px'}
            ),
            dcc.Input(
                id='txt_suffix',
                placeholder='suffix flags',
                type='text',
                style={'width': '100px', 'margin-right': '2px'}
            ),
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
        [Output('cytoscape-elements', 'elements'),
         Output('txt_prefix', 'value'),
         Output('txt_suffix', 'value')],
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
            elements, prefix, suffix = load(io.BytesIO(base64.b64decode(contents.split(',')[1])))
            return elements, prefix, suffix
        elif ctx.triggered_id == 'btn-add':
            elements = add_node(elements, txt_node)
        elif ctx.triggered_id == 'btn-remove':
            elements = remove(elements, selected_nodes, selected_edges)
        elif ctx.triggered_id == 'btn-connect':
            elements = connect_nodes(elements, selected_nodes)
        elif ctx.triggered_id == 'btn-update':
            elements = update_node(elements, selected_nodes, txt_node)
        return elements, dash.no_update, dash.no_update

    @app.callback(
        [Output('cytoscape-elements', 'elements'),
        Output('txt_prefix', 'value'),
        Output('txt_suffix', 'value'),
        Output('pipeline-output', 'children'),
        Output('pipeline-file-store', 'data')],
        [Input('upload-data', 'contents')],
        [State('upload-data', 'filename')],
        prevent_initial_call=True
    )
    def update_pipeline_upload(contents, filename):
        if contents and filename:
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            elements, prefix, suffix = load(io.BytesIO(decoded))
            preview = decoded.decode('utf-8')[:500]
            if len(decoded) > 500:
                preview += '...'
            return elements, prefix, suffix, f"Pipeline File: {filename}\n\n{preview}", filename
        raise dash.exceptions.PreventUpdate

    @app.callback(
        Output('download-data', 'data'),
        [Input('btn-download', 'n_clicks')],
        [State('cytoscape-elements', 'elements'),
         State('txt_prefix', 'value'),
         State('txt_suffix', 'value')],
        prevent_initial_call=True
    )
    def save_data(n_clicks, elements, prefix, suffix):
        # Build the DiGraph
        G = nx.DiGraph()
        G.graph['prefix'] = prefix or ""
        G.graph['suffix'] = suffix or ""
        for el in elements:
            d = el['data']
            if 'source' in d:
                G.add_edge(d['source'], d['target'], id=d.get('id'))
            else:
                G.add_node(
                    d['id'],
                    label=d.get('label', d['id']),
                    **el.get('position', {})
                )

        # Dump directly to bytes
        buf = io.BytesIO()
        nx.write_graphml(G, buf)
        buf.seek(0)
        return dcc.send_bytes(buf.read(), 'network_data.graphml')

    @app.callback(
        Output('btn-runproc', 'n_clicks'),
        [Input('btn-runproc', 'n_clicks')],
        [State('cytoscape-elements', 'elements'),
         State('cytoscape-elements', 'selectedNodeData')],
        prevent_initial_call=True
    )

    @app.callback(
        Output('btn-runproc', 'n_clicks'),
        [Input('btn-runproc', 'n_clicks')],
        [State('cytoscape-elements', 'elements'),
        State('cytoscape-elements', 'selectedNodeData'),
        State('txt_prefix', 'value'),
        State('txt_suffix', 'value')],
        prevent_initial_call=True
    )
    def run_process(n_clicks, elements, selected_data, prefix, suffix):
        G = nx.DiGraph()
        for el in elements:
            d = el['data']
            if 'source' in d:
                G.add_edge(d['source'], d['target'], id=d.get('id'))
            else:
                G.add_node(d['id'], label=d.get('label', d['id']), **el.get('position', {}))
        G.graph['prefix'] = prefix or 'bash -c'
        G.graph['suffix'] = suffix or ''
        execute_process(selected_data, G)
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
    elements, _, _ = load(io.BytesIO(decoded))
    return elements

def load(pipeline_file):
    G = nx.read_graphml(pipeline_file)
    prefix = G.graph.get('prefix', '')
    suffix = G.graph.get('suffix', '')

    elements = []
    for node_id, node_data in G.nodes(data=True):
        node_el = {
            'data': {
                'id': node_id,
                'label': node_data.get('label', node_id)
            },
            'position': {
                'x': float(node_data.get('x', 0)),
                'y': float(node_data.get('y', 0))
            }
        }
        elements.append(node_el)

    for source, target, edge_data in G.edges(data=True):
        edge_el = {
            'data': {
                'id': edge_data.get('id', f'{source}-{target}'),
                'source': source,
                'target': target
            }
        }
        elements.append(edge_el)

    return elements, prefix, suffix


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

def execute_process(data, G):
    prefix = G.graph.get('prefix', 'bash -c')  # Default to 'bash -c'
    suffix = G.graph.get('suffix', '')  # Default to empty string
    if data:
        for process in data:
            command = f"{prefix} \"{process['label']}\" {suffix}"
            subprocess.call(command, shell=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="workforce",
        description="Manage and run graph-based workflows."
    )
    parser.add_argument("filename", nargs="?", help="Optional GraphML file to load")
    args = parser.parse_args()
    Gui(args.filename)

