#!/usr/bin/env python3
from multiprocessing import Process
from pathlib import Path
from time import time
import argparse
import logging
import math
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import subprocess

class worker:
    ''' A method for running bash processes in parallel according to a csv file instructions '''
    def __init__(self, instructions):
        # Load attributes
        self.init_time = str(time())
        self.instruction_file = instructions

        # Set up logging
        logging.basicConfig(filename=str(Path.home())+"/workforce/workforce.log", filemode="a", format="%(created).6f,"+self.init_time+",%(processName)s,%(message)s", level=logging.INFO)
        logging.info("begin work")

        # Read instructions
        logging.info("loading %s",instructions) 
        if not self.instruction_file:
            logging.error("no instructions file supplied")
            quit()
        self.instructions = pd.read_csv(instructions,names=["source","target"], na_filter=False)
        self.instructions["weight"] = 1
        logging.info("instructions loaded")

        # Graph instructions
        logging.info("begin instruction graphing")
        self.graph(self.instructions)
        logging.info("instructions graphed")
        logging.info("init complete")

    def graph(self, df):
        # Create graph based on a dataframe
        Graphtype = nx.DiGraph()
        G = nx.from_pandas_edgelist(df, edge_attr='weight', create_using=Graphtype)
        M = G.number_of_edges()
        edge_colors = range(2, M + 2)
        edge_alphas = [(5 + i) / (M + 4) for i in range(M)]
        plt.figure(figsize=(10, 7))
        nx.draw(G, pos=nx.spring_layout(G,k=5/math.sqrt(G.order())), with_labels=True, edge_color=edge_colors, edge_cmap=plt.cm.Blues, width=2, font_size=10)
        plt.savefig(self.instruction_file+".pdf")

    def run(self):
        # Run loaded instructions from the first row
        logging.info("begin work")
        def task(curr):
            jobs = []
            logging.info("running %s", curr) 
            subprocess.run(curr, shell=True)
            for i in self.instructions.loc[self.instructions["source"] == curr].index:
                t = Process(target=task, args=[self.instructions.iloc[i]["target"]])
                jobs.append(t)
                t.start()
            for j in jobs:
                j.join()
        task(self.instructions.iloc[0]["source"])
        logging.info("work completed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--instructions")
    args = parser.parse_args()

    current_worker = worker(args.instructions)
    current_worker.run()
