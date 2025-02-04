#!/usr/bin/env python3

from dash import Dash, html, dcc, Input, Output, State, ctx
import dash_cytoscape as cyto
import base64
import io
import json
import networkx as nx
from networkx.readwrite import json_graph
import datetime
import subprocess
import webbrowser

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
        ], style={'display': 'flex', 'gap': '5px'}),
        html.Div([
            dcc.Input(id='txt_node', value='echo "Input bash command"', type='text', style={'width': '400px'}),
            html.Button('+', id='btn-add', n_clicks=0, style={'background-color': 'lightgreen'})
        ], style={'margin-top': '5px'}),
        html.Hr(),
        cyto.Cytoscape(
            id='cytoscape-elements',
            layout={'name': 'preset'},
            style={'width': '100%', 'height': '85vh'},
            stylesheet=create_stylesheet(),
            elements=[],
        ),
        html.Hr(),
        'workforce: ' + str(datetime.datetime.now()),
    ])

def create_stylesheet():
    return [
        {'selector': 'node', 'style': {'label': 'data(label)', 'background-color': 'lightgray'}},
        {'selector': 'node:selected', 'style': {'background-color': 'gray'}},
        {'selector': 'edge', 'style': {'curve-style': 'bezier', 'target-arrow-shape': 'triangle'}},
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
         State('cytoscape-elements', 'elements'),
         State('cytoscape-elements', 'selectedNodeData')],
        prevent_initial_call=True
    )
    def modify_network(contents, add_clicks, remove_clicks, connect_clicks, update_clicks, txt_node, elements, selected_nodes):
        if ctx.triggered_id == 'upload-data':
            elements = handle_upload(contents)
        elif ctx.triggered_id == 'btn-add':
            elements = add_node(elements, txt_node)
        elif ctx.triggered_id == 'btn-remove':
            elements = remove_node(elements, selected_nodes)
        elif ctx.triggered_id == 'btn-connect':
            elements = connect_nodes(elements, selected_nodes)
        elif ctx.triggered_id == 'btn-update':
            elements = update_node(elements, selected_nodes, txt_node)
        return elements

def handle_upload(contents):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    return load(io.BytesIO(decoded))

def load(pipeline_file):
    G = nx.read_graphml(pipeline_file)
    graph = json_graph.node_link_data(G)
    return [{'data': {'id': node['id'], 'label': node.get('label', node['id'])}, 'position': {'x': 0, 'y': 0}} for node in graph['nodes']]

def add_node(elements, txt_node):
    new_id = f'node{len(elements) + 1}'
    elements.append({'data': {'id': new_id, 'label': txt_node}})
    return elements

def remove_node(elements, selected_nodes):
    selected_ids = {node['id'] for node in selected_nodes} if selected_nodes else set()
    return [el for el in elements if el['data']['id'] not in selected_ids]

def connect_nodes(elements, selected_nodes):
    if len(selected_nodes) < 2:
        return elements
    source = selected_nodes[0]['id']
    target = selected_nodes[1]['id']
    elements.append({'data': {'source': source, 'target': target, 'id': f'{source}-{target}'}})
    return elements

def update_node(elements, selected_nodes, txt_node):
    if selected_nodes:
        selected_id = selected_nodes[0]['id']
        for element in elements:
            if element['data']['id'] == selected_id:
                element['data']['label'] = txt_node
                break
    return elements

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("pipeline", nargs='?')
    args = parser.parse_args()
    gui(args.pipeline)

