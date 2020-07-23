#!/usr/bin/env python3
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

def graph(plan_file):
    # Create graph based on a dataframe

    df = pd.read_csv(plan_file,
    Graphtype = nx.DiGraph()
    G = nx.from_pandas_edgelist(df, edge_attr='weight', create_using=Graphtype)
    M = G.number_of_edges()
    edge_colors = range(2, M + 2)
    edge_alphas = [(5 + i) / (M + 4) for i in range(M)]
    plt.figure(figsize=(10, 7))
    nx.draw(G,
            pos=nx.spring_layout(G,k=5),
            with_labels=True,
            edge_color=edge_colors,
            edge_cmap=plt.cm.Blues,
            width=2,
            font_size=10)
    plt.savefig(self.plan_file+".pdf")
