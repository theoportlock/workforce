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
import xml.etree.ElementTree as ET


def Gui(pipeline_file=None):
    initial_elements = []
    initial_pipeline = ""
    initial_pipeline_file = None

    if pipeline_file:
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
    app.run(debug=True, use_reloader=False)


def create_layout(initial_elements, initial_pipeline, initial_pipeline_file):
    return html.Div([
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
            dcc.Input(id='txt_prefix', placeholder='prefix flags', type='text', style={'width': '100px', 'margin-right': '2px'}),
            dcc.Input(id='txt_suffix', placeholder='suffix flags', type='text', style={'width': '100px', 'margin-right': '2px'}),
            dcc.Store(id='pipeline-file-store', data=initial_pipeline_file)
        ], style={'display': 'flex', 'flex-direction': 'row', 'gap': '2px'}),

        html.Div([
            dcc.Input(id='txt_node', value='echo "Input bash command"', type='text', style={'width': '400px', 'margin-right': '2px'}),
            html.Button('+', id='btn-add', n_clicks=0, style={'margin-right': '2px', 'background-color': 'lightgreen'})
        ], style={'margin-top': '2px'}),

        html.Hr(),

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

        html.Div(id='pipeline-output', children=initial_pipeline, style={'margin-top': '20px', 'white-space': 'pre-wrap'}),
        html.Div('workforce: ' + str(datetime.datetime.now()), style={'margin-top': '10px'})
    ])


def create_stylesheet():
    return [
        {'selector': 'node', 'style': {'label': 'data(label)', 'font-size': '10px', 'width': '30px', 'height': '30px', 'text-max-width': '150px', 'text-wrap': 'wrap', 'background-color': 'lightgray'}},
        {'selector': 'node:selected', 'style': {'background-color': 'gray'}},
        {'selector': 'edge', 'style': {'curve-style': 'bezier', 'target-arrow-shape': 'triangle', 'line-color': 'lightgray', 'target-arrow-color': 'lightgray'}},
        {'selector': 'edge:selected', 'style': {'line-color': 'gray', 'target-arrow-color': 'gray'}},
    ]


def register_callbacks(app):
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
         State('cytoscape-elements', 'selectedNodeData'),
         State('cytoscape-elements', 'selectedEdgeData')],
        prevent_initial_call=True
    )
    def modify_network(contents, add_clicks, remove_clicks, connect_clicks, update_clicks,
                       txt_node, filename, elements, selected_nodes, selected_edges):
        trigger = ctx.triggered_id
        if trigger == 'upload-data' and contents:
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            elements, prefix, suffix = load(io.BytesIO(decoded))
            return elements, prefix, suffix

        if trigger == 'btn-add': elements = add_node(elements, txt_node)
        if trigger == 'btn-remove': elements = remove(elements, selected_nodes, selected_edges)
        if trigger == 'btn-connect': elements = connect_nodes(elements, selected_nodes)
        if trigger == 'btn-update': elements = update_node(elements, selected_nodes, txt_node)

        return elements, dash.no_update, dash.no_update

    @app.callback(
        [Output('pipeline-output', 'children', allow_duplicate=True),
         Output('pipeline-file-store', 'data')],
        Input('upload-data', 'contents'),
        State('upload-data', 'filename'),
        prevent_initial_call=True
    )
    def update_pipeline_upload(contents, filename):
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        preview = decoded.decode('utf-8')[:500] + ('...' if len(decoded) > 500 else '')
        return f"Pipeline File: {filename}\n\n{preview}", filename

    @app.callback(
        Output('download-data', 'data'),
        Input('btn-download', 'n_clicks'),
        State('cytoscape-elements', 'elements'),
        State('txt_prefix', 'value'),
        State('txt_suffix', 'value'),
        prevent_initial_call=True
    )
    def save_data(n_clicks, elements, prefix, suffix):
        G = nx.DiGraph()
        G.graph['prefix'], G.graph['suffix'] = prefix or '', suffix or ''
        for el in elements:
            d = el['data']
            if 'source' in d and 'target' in d:
                G.add_edge(d['source'], d['target'], id=d.get('id'))
            else:
                G.add_node(d['id'], label=d.get('label', d['id']), x=el.get('position', {}).get('x', 0), y=el.get('position', {}).get('y', 0))
        buf = io.BytesIO()
        nx.write_graphml(G, buf)
        buf.seek(0)
        return dcc.send_bytes(buf.read(), filename='Workfile')

    @app.callback(
        Output('pipeline-output', 'children', allow_duplicate=True),
        Input('btn-runproc', 'n_clicks'),
        State('cytoscape-elements', 'elements'),
        State('cytoscape-elements', 'selectedNodeData'),
        State('txt_prefix', 'value'),
        State('txt_suffix', 'value'),
        prevent_initial_call=True
    )
    def run_process(n_clicks, elements, selected_data, prefix, suffix):
        print("Triggered runproc:", ctx.triggered_id)
        G = nx.DiGraph()
        for el in elements:
            d = el['data']
            if 'source' in d:
                G.add_edge(d['source'], d['target'], id=d.get('id'))
            else:
                G.add_node(d['id'], label=d.get('label', d['id']), x=el['position']['x'], y=el['position']['y'])
        G.graph['prefix'], G.graph['suffix'] = prefix or 'bash -c', suffix or ''
        execute_process(selected_data, G)
        return f"Process run on: {selected_data}"

    @app.callback(
        Output('txt_node', 'value'),
        [Input('cytoscape-elements', 'tapNodeData'), Input('btn-clear', 'n_clicks')],
        prevent_initial_call=True
    )
    def update_text_box(tap_node_data, n_clicks):
        if ctx.triggered_id == 'cytoscape-elements' and tap_node_data:
            return tap_node_data['label']
        if ctx.triggered_id == 'btn-clear':
            return ''
        return dash.no_update

    @app.callback(
        Output('btn-view-pipeline', 'n_clicks'),
        Input('btn-view-pipeline', 'n_clicks'),
        State('pipeline-file-store', 'data'),
        prevent_initial_call=True
    )
    def view_pipeline(n_clicks, filename):
        if filename:
            subprocess.run([sys.executable, "-m", "workforce", "view", filename])
        return 0

    @app.callback(
        Output('btn-run-pipeline', 'n_clicks'),
        Input('btn-run-pipeline', 'n_clicks'),
        State('pipeline-file-store', 'data'),
        prevent_initial_call=True
    )
    def run_pipeline(n_clicks, filename):
        if filename:
            subprocess.run([sys.executable, "-m", "workforce", "run", filename])
        return 0

def load(pipeline_file):
    # Read file content
    if isinstance(pipeline_file, (str, bytes)):
        with open(pipeline_file, 'rb') as f:
            content = f.read()
    else:
        content = pipeline_file.read()

    # Use NetworkX to read the graph
    f = io.BytesIO(content)
    G = nx.read_graphml(f)

    # Extract prefix and suffix from graph attributes
    prefix = G.graph.get('prefix', '')
    suffix = G.graph.get('suffix', '')

    # Build cytoscape-compatible elements
    elements = []
    for node_id, node_data in G.nodes(data=True):
        elements.append({
            'data': {
                'id': node_id,
                'label': node_data.get('label', node_id),
                'status': node_data.get('status', '')
            },
            'position': {
                'x': float(node_data.get('x', 0)),
                'y': float(node_data.get('y', 0))
            }
        })

    for source, target, edge_data in G.edges(data=True):
        elements.append({
            'data': {
                'id': edge_data.get('id', f'{source}-{target}'),
                'source': source,
                'target': target
            }
        })

    return elements, prefix, suffix

def add_node(elements, txt_node):
    elements.append({'data': {'id': txt_node, 'label': txt_node, 'status': ''}})
    return elements


def remove(elements, selected_nodes, selected_edges):
    sel_n = {n['id'] for n in (selected_nodes or [])}
    sel_e = {(e['source'], e['target']) for e in (selected_edges or [])}
    return [el for el in elements if not (el['data'].get('id') in sel_n or (el['data'].get('source'), el['data'].get('target')) in sel_e)]


def connect_nodes(elements, selected_nodes):
    if not selected_nodes or len(selected_nodes)<2: return elements
    for i in range(len(selected_nodes)-1): elements.append({'data': {'source': selected_nodes[i]['id'], 'target': selected_nodes[i+1]['id']}})
    return elements


def update_node(elements, selected_nodes, txt):
    if selected_nodes and len(selected_nodes)==1:
        sel=selected_nodes[0]['id']
        for el in elements:
            if el['data'].get('id')==sel: el['data']['label']=txt; break
    return elements


def execute_process(data, G):
    if data:
        for proc in data:
            cmd=f"{G.graph.get('prefix','bash -c')} \"{proc['label']}\" {G.graph.get('suffix','')}"
            subprocess.call(cmd, shell=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="workforce", description="Manage and run graph-based workflows.")
    parser.add_argument("filename", nargs="?", help="Optional GraphML file to load")
    args = parser.parse_args()
    Gui(args.filename)
