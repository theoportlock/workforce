#!/usr/bin/env python3
from dash import Dash, html, Input, Output, State, dcc, ctx
import dash
import base64
import dash_cytoscape as cyto
import datetime
import io
import json
import numpy as np
import pandas as pd
import subprocess
import webbrowser
import networkx as nx
from networkx.readwrite import json_graph

def gui(pipeline_file=None):
    app = Dash(__name__)
    app.title = "Workforce"
    app.layout = create_layout()
    register_callbacks(app)
    if pipeline_file:
        app.layout['cytoscape-elements'].elements = load(pipeline_file)
    webbrowser.open_new('http://127.0.0.1:8050/')
    app.run_server(debug=False, use_reloader=False)

def create_layout():
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
            autoRefreshLayout=False,
            responsive=True,
            elements=[],
            zoomingEnabled=True,
            userZoomingEnabled=True,
            wheelSensitivity=0.1,
        ),
        html.Hr(),
        'workforce: ' + str(datetime.datetime.now()),
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
    @app.callback(
        Output('cytoscape-elements', 'elements'),
        [Input('upload-data', 'contents'),
         Input('btn-add', 'n_clicks'),
         Input('btn-remove', 'n_clicks'),
         Input('btn-connect', 'n_clicks'),
         Input('btn-update', 'n_clicks')],
        [State('txt_node', 'value'),
         State('upload-data', 'filename'),
         State('upload-data', 'last_modified'),
         State('cytoscape-elements', 'elements'),
         State("cytoscape-elements", "selectedNodeData"),
         State("cytoscape-elements", "selectedEdgeData")],
        prevent_initial_call=True
    )
    def modify_network(contents, add_clicks, remove_clicks, connect_clicks, update_clicks, txt_node, filename, last_modified, elements, selected_nodes, selected_edges):
        if ctx.triggered_id == 'upload-data':
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
    @app.callback(
        Output('download-data', 'data'),
        [Input('btn-download', 'n_clicks')],
        [State('cytoscape-elements', 'elements')],
        prevent_initial_call=True
    )
    def save_data(n_clicks, elements):
        return save_elements(elements)
    @app.callback(
        Output('cytoscape-elements', 'btn-runproc'),
        [Input('btn-runproc', 'n_clicks')],
        [State('cytoscape-elements', 'selectedNodeData')],
        prevent_initial_call=True
    )
    def run_process(n_clicks, data):
        execute_process(data)
        return dash.no_update
    @app.callback(
        Output('txt_node', 'value'),
        [Input('cytoscape-elements', 'tapNodeData'),
         Input('btn-clear', 'n_clicks')],
        prevent_initial_call=True
    )
    def update_text_box(tap_node_data, n_clicks):
        if ctx.triggered_id == 'cytoscape-elements':
            text = tap_node_data['label']
            #print(n_clicks) # Just for testing
        elif ctx.triggered_id == 'btn-clear':
            text = ''
        return text

def handle_upload(contents):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    elements = load(io.BytesIO(decoded))
    return elements

def load(pipeline_file):
    # Reads graphml format and converts to dash-cytoscape json using nx
    G = nx.read_graphml(pipeline_file)
    graph = json_graph.node_link_data(G)
    elements = graph['nodes'] + graph['links']
    dash_cytoscape_data = []
    for element in elements:
        if 'source' in element and 'target' in element:
            updated_element = {
                'data': {
                    'source': element.get('source'),
                    'target': element.get('target'),
                    'id': element.get('id')
                }
            }
        else:
            updated_element = {
                'data': {
                    'label': element.get('label'),
                    'id': element.get('id')
                },
                'position': {
                    'x': float(element.get('x', 0)),
                    'y': float(element.get('y', 0))
                }
            }
        dash_cytoscape_data.append(updated_element)
    return dash_cytoscape_data

def add_node(elements, txt_node):
    elements.append({'data':{'label':txt_node}})
    return elements

def remove(elements, selected_nodes, selected_edges):
    selected_node_labels = {node['label'] for node in selected_nodes} if selected_nodes else set()
    selected_edge_pairs = {(edge['source'], edge['target']) for edge in selected_edges} if selected_edges else set()
    elements = [
        el for el in elements
        if el['data'].get('label') not in selected_node_labels and
           (el['data'].get('source'), el['data'].get('target')) not in selected_edge_pairs
    ]
    return elements

def connect_nodes(elements, selected_nodes):
    if len(selected_nodes) < 2:
        return elements
    for i in range(len(selected_nodes) - 1):
        source_node = selected_nodes[i]['id']
        target_node = selected_nodes[i + 1]['id']
        elements.append({'data': {'source': source_node, 'target': target_node}})
    return elements

def update_node(elements, selected_nodes, txt_node_value):
    if len(selected_nodes) == 1:
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
            G.add_edge(data['source'], data['target'], id=data['id'])
        else:
            node_id = data['id']
            label = data.get('label', node_id)
            pos = element.get('position', {})
            G.add_node(node_id, label=label, x=pos.get('x', 0), y=pos.get('y', 0))
    graphml_bytes = io.BytesIO()
    nx.write_graphml(G, graphml_bytes)
    graphml_bytes.seek(0)
    return dcc.send_string(graphml_bytes.getvalue().decode('utf-8'), 'network_data.graphml')

def execute_process(data):
    for process in data:
        subprocess.call(process['label'], shell=True)

if __name__ == '__main__':
    import argparse
    import sys
    from workforce import worker
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--run", required=False)
    parser.add_argument("pipeline", nargs='?')
    args = parser.parse_args()
    if args.run:
        worker(args.run)
    elif args.pipeline:
        gui(args.pipeline)
    else:
        gui()
