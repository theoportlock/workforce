#!/usr/bin/env python3

from datetime import datetime
from multiprocessing import Process, Queue
from pathlib import Path
import argparse
import importlib as il
import logging
import pandas as pd
import subprocess

class run:
    ''' A method for running bash processes in parallel according to a csv file schema '''
    def __init__(self, functionsdir, schema, graph):
        # Set up logging
        logging.basicConfig(filename=schema[0]+".log",
                filemode="a",
                format= "%(asctime)s %(processName)s: %(message)s",
                level=logging.INFO, datefmt="%H:%M:%S")
        if not schema:
            logging.error("no schema loaded")
            quit()
        else:
            logging.info("loading %s", schema[0])
            # Read schema (first of the remainer of args)
            self.schema = pd.read_csv(schema[0],names=["source","target"])
            self.schema["weight"] = 1
            logging.info("done")

            if graph:
                # Create graph - have to install graphviz and networkx for this - produces if you give the g flag
                import matplotlib.pyplot as plt
                import networkx as nx
                Graphtype = nx.Graph()
                G = nx.from_pandas_edgelist(self.schema, edge_attr='weight', create_using=Graphtype)
                pos = nx.layout.spring_layout(G)
                M = G.number_of_edges()
                edge_colors = range(2, M + 2)
                edge_alphas = [(5 + i) / (M + 4) for i in range(M)]
                nx.draw(G, with_labels=True, edge_color=edge_colors, edge_cmap=plt.cm.Blues, width=3)
                #plt.show()
                plt.savefig(schema[0]+".pdf")
            
        # Load additional functions in a directory if necessary
        if functionsdir:
            logging.info("loading functions in supplied directories")
            functions = subprocess.check_output(['ls',functionsdir]).splitlines()
            functions = [i.decode() for i in functions]
            for i in self.schema.index:
                for j in ("source","target"):
                    if self.schema[j][i] not in functions:
                        logging.warning("function " + self.schema[j][i] + " not found")
                    else:
                        logging.info("function " + self.schema[j][i] + " found")
                        self.schema.loc[i,j] = functionsdir + "/" + self.schema[j][i]

            logging.info("done")
        else:
            functions = []

        logging.info("init complete")

    def excecute(self):
        # run loaded schema
        def task(curr):
            jobs = []
            logging.info("running %s", curr) 
            subprocess.run(curr,shell=True)
            for i in self.schema.loc[self.schema["source"] == curr].index:
                t = Process(target=task, args=[self.schema.iloc[i]["target"]])
                jobs.append(t)
                t.start()
            for j in jobs:
                j.join()

        logging.info("begin excecution")
        # start run with first row of schema
        task(self.schema.iloc[0]["source"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--functionsdir')
    parser.add_argument('-g', '--graph', action='store_true')
    parser.add_argument('schema', nargs=argparse.REMAINDER)
    args = parser.parse_args()

    currentrun = run(args.functionsdir, args.schema, args.graph)
    currentrun.excecute()
