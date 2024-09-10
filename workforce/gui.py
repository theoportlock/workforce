#/usr/bin/env python3
from dash import Dash, html, Input, Output, State, dcc, ctx
import base64
import dash_cytoscape as cyto
import datetime
import io
import numpy as np
import pandas as pd
import subprocess
import webbrowser

def gui(pipeline_file=None):
    app = Dash(__name__)
    app.title = "Workforce"
    app.layout = create_layout()
    if pipeline_file:
        edges = pd.read_csv(pipeline_file,
                            sep='\t',
                            header=None).set_axis(['source','target'], axis=1)
        elements = edges_to_elements(edges)
        app.layout['cytoscape-elements'].elements = elements
    register_callbacks(app)
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
            html.Button('Swap', id='btn-swap', n_clicks=0),
        ], style={'display': 'flex', 'flex-direction': 'row', 'gap': '2px'}),
        html.Div([
            dcc.Input(id='txt_from', value='echo "from"', type='text', style={'width': '400px', 'margin-right': '2px'}),
            dcc.Input(id='txt_to', value='echo "to"', type='text', style={'width': '400px', 'margin-right': '2px'}),
            html.Button('+', id='btn-add', n_clicks=0, style={'margin-right': '2px', 'background-color': 'lightgreen'})
        ], style={'margin-top': '2px'}),
        html.Hr(),
        cyto.Cytoscape(
            id='cytoscape-elements',
            layout={'name': 'breadthfirst', 'directed': True},
            style={'width': '100%', 'height': '85vh'},
            stylesheet=create_stylesheet(),
            autoRefreshLayout=True,
            responsive=True,
            elements=[]
        ),
        html.Hr(),
        'workforce: ' + str(datetime.datetime.now()),
    ])

def create_stylesheet():
    return [
        {
            'selector': 'node',
            'style': {
                'label': 'data(id)',
                'font-size': '13px',
                'width': '30px',
                'height': '30px',
                'text-max-width': '250px',
                "text-wrap": "wrap",
                },
        },
        {
            'selector': 'edge',
            'style': {
                'curve-style': 'taxi',
                'target-arrow-shape': 'triangle',
                'line-color': 'lightgray',
            }
        }
    ]

def register_callbacks(app):
    @app.callback(
        Output('cytoscape-elements', 'elements'),
        [Input('upload-data', 'contents'),
         Input('btn-add', 'n_clicks'),
         Input('btn-remove', 'n_clicks')],
        [State('txt_from', 'value'),
         State('txt_to', 'value'),
         State('upload-data', 'filename'),
         State('upload-data', 'last_modified'),
         State('cytoscape-elements', 'elements'),
         State("cytoscape-elements", "selectedNodeData")],
        prevent_initial_call=True
    )
    def modify_network(contents, add_clicks, remove_clicks, txt_from, txt_to, filename, last_modified, elements, selected):
        if ctx.triggered_id == 'upload-data':
            elements = handle_upload(contents)
        elif ctx.triggered_id == 'btn-add':
            elements = add_node(elements, txt_from, txt_to)
        elif ctx.triggered_id == 'btn-remove':
            elements = remove_node(elements, selected)
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

    @app.callback(
        [Output('txt_from', 'value'),
         Output('txt_to', 'value')],
        [Input('cytoscape-elements', 'tapEdgeData'),
         Input('btn-swap', 'n_clicks')],
        [State('txt_to', 'value'),
         State('txt_from', 'value')],
        prevent_initial_call=True
    )
    def update_text_boxes(tap_edge_data, n_clicks, txt_to, txt_from):
        if ctx.triggered_id == 'btn-swap':
            return txt_to, txt_from
        elif ctx.triggered_id == 'cytoscape-elements':
            return tap_edge_data['source'], tap_edge_data['target']

def handle_upload(contents):
    edges = decode(contents)
    if edges is not None:
        return edges_to_elements(edges)
    else:
        return []

def decode(contents):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        edges = pd.read_csv(io.StringIO(decoded.decode('utf-8')), sep='\t', header=None).set_axis(['source','target'], axis=1)
    except:
        edges = None
    return edges

def add_node(elements, txt_from, txt_to):
    edges = elements_to_edges(elements)
    edges = pd.concat([edges, pd.DataFrame([txt_from, txt_to], index=['source', 'target']).T], axis=0, ignore_index=True).drop_duplicates()
    return edges_to_elements(edges)

def remove_node(elements, selected):
    if not selected:
        return elements
    else:
        edges = elements_to_edges(elements)
        edges = edges.loc[(edges['source'] != selected[0]['id']) & (edges['target'] != selected[0]['id'])]
        return edges_to_elements(edges)

def save_elements(elements):
    ele = pd.concat([pd.DataFrame.from_dict(i) for i in elements], axis=1).T.set_index('id')
    edges = ele.drop('label', axis=1).dropna().set_index('source')
    return dcc.send_data_frame(edges.to_csv, 'mydf.tsv', sep='\t', header=False)

def elements_to_edges(elements):
    if not elements:
        return pd.DataFrame()
    ele = pd.concat([pd.DataFrame.from_dict(i) for i in elements], axis=1).T.set_index('id')
    edges = ele.drop('label', axis=1).dropna().reset_index(drop=True)
    return edges

def edges_to_elements(edges):
    nodes = np.concatenate([edges['source'].unique(), edges['target'].unique()])
    nodes = [{'data': {'id': name, 'label': name}} for name in nodes]
    edges = [
        {'data': {'source': source, 'target': target}}
        for source, target in edges[['source','target']].values
    ]
    elements = edges + nodes
    return elements

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
