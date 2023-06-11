from dash import Dash, html, Input, Output, State, dcc, ctx
import dash_cytoscape as cyto
import numpy as np
import pandas as pd

def gui():
    app = Dash(__name__)

    # define app
    app.layout = html.Div([
        html.Div([
                dcc.Upload(html.Button('Load'), id='upload-data'),
                html.Button('Save', id='btn-download'), dcc.Download(id='download-data')],
                ),
        html.Div(['Input: ',
                  dcc.Input(id='txt_from', value='from', type='text'),
                  dcc.Input(id='txt_to', value='to', type='text')
                  ]),
        html.Div([
            html.Button('Add Node', id='btn-add', n_clicks=0),
            html.Button('Remove Node', id='btn-remove', n_clicks=0),
        ]),
        cyto.Cytoscape(
            id='cytoscape-elements',
            layout={'name': 'breadthfirst'},
            style={'width': '100%', 'height': '450px'},
            elements=[]
        )
    ])

    # Update Graph through load or add
    @app.callback(Output('cytoscape-elements', 'elements'),
                  Input('upload-data', 'contents'),
                  Input('btn-add', 'n_clicks_timestamp'),
                  Input('txt_from', 'value'),
                  Input('txt_to', 'value'),
                  State('upload-data', 'filename'),
                  State('upload-data', 'last_modified'),
                  State('cytoscape-elements', 'elements'),
                  prevent_initial_call=True)
    def load_data(contents, n_clicks, txt_from, txt_to, filename, last_modified, elements):
        # For data load
        if ctx.triggered_id == 'upload-data':
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
            edges = elements_to_edges(elements)
            edges = pd.concat([edges, pd.DataFrame([txt_from,txt_to], index=['source','target']).T], axis=0, ignore_index=True).drop_duplicates()
            elements = edges_to_elements(edges)
        return elements

    # Save data
    @app.callback(Output('download-data', 'data'),
                  Input('btn-download', 'n_clicks'),
                  State('cytoscape-elements', 'elements'),
                  prevent_initial_call=True)
    def save_data(n_clicks, elements):
        ele = pd.concat([pd.DataFrame.from_dict(i) for i in elements], axis=1).T.set_index('id')
        edges = ele.drop('label', axis=1).dropna().set_index('source')
        return dcc.send_data_frame(edges.to_csv, 'mydf.csv')

    # Other functions
    def parse_contents(contents, filename):
        import base64
        import io
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        try:
            if 'csv' in filename:
                df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), names=['source','target'])
            if 'tsv' in filename:
                df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), sep='\t', names=['source','target'])
            elif 'xls' in filename:
                df = pd.read_excel(io.BytesIO(decoded), names=['source','target'])
        except Exception as e:
            return html.Div([
                'There was an error processing the edgelist'
            ])
        return df

    def elements_to_edges(elements):
        ele = pd.concat([pd.DataFrame.from_dict(i) for i in elements], axis=1).T.set_index('id')
        edges = ele.drop('label', axis=1).dropna().reset_index(drop=True)
        return edges

    def edges_to_elements(edges):
        nodes = np.concatenate([edges.source.unique(), edges.target.unique()])
        nodes = [{'data': {'id': name, 'label': name}} for name in nodes]
        edges = [
            {'data': {'source': source, 'target': target}}
            for source, target in edges[['source','target']].values
        ]
        elements = edges+nodes
        return elements

    app.run_server()
