#!/usr/bin/env python3
from datetime import datetime
from multiprocessing import Process, Queue
from pathlib import Path
from time import time
import argparse
import importlib as il
import logging
import math
import pandas as pd
import subprocess

class worker:
    ''' A method for running bash processes in parallel according to a csv file instructions '''
    def __init__(self, instructions, functionsdir=False, graph=False):
        # Set up logging
        self.init_time = str(time())
        self.functionsdir = functionsdir
        self.instruction_file = instructions
        self.graph = graph
        logging.basicConfig(filename=instructions+".log",
                filemode="a",
                format= "%(created).6f," + self.init_time + ",%(processName)s,%(message)s",
                level=logging.INFO)
        if not self.instruction_file:
            logging.error("no instructions file supplied")
            quit()
        else:
            logging.info("loading instructions") 
            # Read instructions (first of the remainer of args)
            self.instructions = pd.read_csv(instructions,names=["source","target"], na_filter=False)
            self.instructions["weight"] = 1
            logging.info("done")

            if self.graph:
                # Create graph - have to install graphviz and networkx for this - produces if you give the g flag
                import matplotlib.pyplot as plt
                import networkx as nx
                Graphtype = nx.DiGraph()
                G = nx.from_pandas_edgelist(self.instructions, edge_attr='weight', create_using=Graphtype)
                pos = nx.layout.spring_layout(G)
                M = G.number_of_edges()
                edge_colors = range(2, M + 2)
                edge_alphas = [(5 + i) / (M + 4) for i in range(M)]
                plt.figure(figsize=(10, 7))
                nx.draw(G, pos=nx.spring_layout(G,k=5/math.sqrt(G.order())), with_labels=True, edge_color=edge_colors, edge_cmap=plt.cm.Blues, width=2, font_size=10)
                #plt.show()
                plt.savefig(instructions+".pdf")
            
        # Load additional functions in a directory if necessary
        if self.functionsdir:
            logging.info("loading functions in supplied directories")
            functions = subprocess.check_output(['ls',self.functionsdir]).splitlines()
            functions = [i.decode() for i in functions]
            for i in self.instructions.index:
                for j in ("source", "target"):
                    if self.instructions[j][i] not in functions:
                        logging.warning("function " + self.instructions[j][i] + " not found")
                    else:
                        logging.info("function " + self.instructions[j][i] + " found")
                        self.instructions.loc[i,j] = self.functionsdir + "/" + self.instructions[j][i]

            logging.info("done")
        else:
            functions = []

        logging.info("init complete")

    def run(self):
        # run loaded instructions
        def task(curr):
            jobs = []
            logging.info("running %s", curr) 
            subprocess.run(curr,shell=True)
            for i in self.instructions.loc[self.instructions["source"] == curr].index:
                t = Process(target=task, args=[self.instructions.iloc[i]["target"]])
                jobs.append(t)
                t.start()
            for j in jobs:
                j.join()

        logging.info("begin excecution")
        # start run with first row of instructions
        task(self.instructions.iloc[0]["source"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--instructions")
    parser.add_argument("-f", "--functionsdir")
    parser.add_argument("-g", "--graph", action="store_true")
    args = parser.parse_args()

    current_worker = worker(args.instructions, args.functionsdir, args.graph)
    current_worker.run()
