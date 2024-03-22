from dash import Dash, html, Input, Output, State, dcc, ctx
import base64
import dash_cytoscape as cyto
import io
import subprocess
import numpy as np
import pandas as pd

def setup_gui():
    app = Dash(__name__)
    app.layout = create_layout()
    register_callbacks(app)
    app.run_server()

def create_layout():
    layout = html.Div([
        html.Div([
            dcc.Upload(html.Button('Load'), id='upload-data'),
            html.Button('Save', id='btn-download'),
            dcc.Download(id='download-data')
        ]),
        html.Div(['Input: ',
            dcc.Input(id='txt_from', value='from', type='text'),
            dcc.Input(id='txt_to', value='to', type='text')
        ]),
        html.Div([
            html.Button('Add Node', id='btn-add', n_clicks=0),
            html.Button('Remove Node', id='btn-remove', n_clicks=0),
            html.Button('Run Process', id='btn-run', n_clicks=0),
        ]),
        html.Hr(),
        cyto.Cytoscape(
            id='cytoscape-elements',
            layout={'name': 'breadthfirst', 'directed': True},
            style={'width': '100%', 'height': '650px'},
            stylesheet=create_stylesheet(),
            elements=[]
        ),
        html.Hr()
    ])
    return layout

def create_stylesheet():
    return [
        {
            'selector': 'node',
            'style': {
                'label': 'data(id)',
                'font-size': '14px',
                'width': '30px',
                'height': '30px',
            }
        },
        {
            'selector': 'edge',
            'style': {
                'curve-style': 'taxi',
                'target-arrow-shape': 'triangle',
            }
        }
    ]

def register_callbacks(app):
    @app.callback(
        Output('cytoscape-elements', 'elements'),
        [Input('upload-data', 'contents'),
         Input('btn-add', 'n_clicks_timestamp'),
         Input('btn-remove', 'n_clicks_timestamp'),
         Input('txt_from', 'value'),
         Input('txt_to', 'value')],
        [State('upload-data', 'filename'),
         State('upload-data', 'last_modified'),
         State('cytoscape-elements', 'elements'),
         State("cytoscape-elements", "selectedNodeData")],
        prevent_initial_call=True
    )
    def load_data(contents, add_clicks, remove_clicks, txt_from, txt_to, filename, last_modified, elements, selected):
        # For data load
        if ctx.triggered_id == 'upload-data':
            elements, edges, nodes =[], [], []
            edges = parse_contents(contents, filename)
            nodes = np.concatenate([edges.source.unique(), edges.target.unique()])
            nodes = [{'data': {'id': name, 'label': name}} for name in nodes]
            edges = [
                {'data': {'source': source, 'target': target}}
                for source, target in edges[['source','target']].values
            ]
            elements = edges+nodes
        # For adding data
        elif ctx.triggered_id == 'btn-add':
            edges = elements_to_edges(elements) if elements else pd.DataFrame()
            edges = pd.concat([edges, pd.DataFrame([txt_from,txt_to], index=['source','target']).T], axis=0, ignore_index=True).drop_duplicates()
            elements = edges_to_elements(edges)
        elif ctx.triggered_id == 'btn-remove':
            if selected[0]:
                edges = elements_to_edges(elements) if elements else pd.DataFrame()
                edges = edges.loc[(edges.source != selected[0]['id']) & (edges.target != selected[0]['id'])]
                elements = edges_to_elements(edges)
        return elements
    @app.callback(
        Output('download-data', 'data'),
        [Input('btn-download', 'n_clicks')],
        [State('cytoscape-elements', 'elements')],
        prevent_initial_call=True
    )
    def save_data(n_clicks, elements):
        ele = pd.concat([pd.DataFrame.from_dict(i) for i in elements], axis=1).T.set_index('id')
        edges = ele.drop('label', axis=1).dropna().set_index('source')
        return dcc.send_data_frame(edges.to_csv, 'mydf.tsv', sep='\t', header=False)
    @app.callback(
        Output('cytoscape-elements', 'btn-run'),
        [Input('btn-run', 'n_clicks')],
        [State('cytoscape-elements', 'selectedNodeData')],
        prevent_initial_call=True
    )
    def display_tapped_node_data(n_clicks, data):
        for process in data:
            #os.system(process['label'])
            subprocess.call(process['label'], shell=True)

def edges_to_elements(edges):
    nodes = np.concatenate([edges.source.unique(), edges.target.unique()])
    nodes = [{'data': {'id': name, 'label': name}} for name in nodes]
    edges = [
        {'data': {'source': source, 'target': target}}
        for source, target in edges[['source','target']].values
    ]
    elements = edges+nodes
    return elements

def elements_to_edges(elements):
    ele = pd.concat([pd.DataFrame.from_dict(i) for i in elements], axis=1).T.set_index('id')
    edges = ele.drop('label', axis=1).dropna().reset_index(drop=True)
    return edges

def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if 'csv' in filename:
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), header=None).set_axis(['source','target'], axis=1)
        elif 'tsv' in filename:
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), sep='\t', header=None).set_axis(['source','target'], axis=1)
        elif 'xls' in filename:
            df = pd.read_excel(io.BytesIO(decoded))
    except Exception as e:
        return html.Div([
            'There was an error processing this file.'
        ])
    return df

setup_gui()
