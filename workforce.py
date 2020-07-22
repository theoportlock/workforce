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
    ''' A method for running bash processes in parallel according to a csv file plan '''
    def __init__(self, plan):
        # Load attributes
        self.init_time = str(time())
        self.plan_file = plan

        # Set up logging
        logging.basicConfig(filename=str(Path.home())+"/workforce/run.log", filemode="a", format="%(created).6f,"+self.init_time+",%(processName)s,%(message)s", level=logging.INFO)
        logging.info("begin init")

        # Read plan
        logging.info("loading %s",plan) 
        if not self.plan_file:
            logging.error("no plan file supplied")
            quit()
        self.plan = pd.read_csv(self.plan_file, names=["source","target"], na_filter=False)
        self.plan["weight"] = 1
        logging.info("plan loaded")

        # Graph plan
        logging.info("begin plan graphing")
        self.graph(self.plan)
        logging.info("plan graphed")
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
        plt.savefig(self.plan_file+".pdf")

    def run(self):
        # Run loaded plan from the first row
        logging.info("begin work")
        def task(curr):
            jobs = []
            logging.info("running %s", curr) 
            subprocess.run(curr, shell=True)
            for i in self.plan.loc[self.plan["source"] == curr].index:
                t = Process(target=task, args=[self.plan.iloc[i]["target"]])
                jobs.append(t)
                t.start()
            for j in jobs:
                j.join()
        task(self.plan.iloc[0]["source"])
        logging.info("work complete")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    # if args.plan:
    current_worker = worker(args.plan[0])
    current_worker.run()
