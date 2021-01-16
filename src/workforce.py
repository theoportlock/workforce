#!/usr/bin/env python
from multiprocessing import Process
from pathlib import Path
from time import time
import argparse
import csv
import logging
import os
import subprocess

class worker:
    def __init__(self, plan_file):
        # Load plan
        self.plan_file = plan_file
        with open(self.plan_file) as csvfile:
            self.plan = list(csv.reader(csvfile, skipinitialspace=True))

    def graph(self):
        # Create graph based on a dataframe
        import networkx as nx
        G = nx.MultiDiGraph()
        G.add_edges_from((({'' : '#'}.get(i, i), {'' : '#'}.get(j, j)) for (i, j) in self.plan))
        nx.drawing.nx_pydot.write_dot(G, self.plan_file + ".dot")

    def run(self):
        # Run loaded plan beginning from the first row
        self.init_time = str(time())
        logging.basicConfig(
                filename=str(Path.home())+"/workforce/log.csv",
                filemode="a",
                format="%(created).6f, "+self.init_time+", "+str(os.getpid())+", %(processName)s, %(message)s",
                level=logging.INFO)
        logging.info("start %s", self.plan_file)

        def begin():
            def task(curr):
                logging.info("%s, running", curr)
                subprocess.call(curr, shell=True)
                logging.info("%s, complete", curr)
                for i in [k[1] for k in self.plan if k[0] == curr]:
                    Process(target=task, args=[i]).start()
            logging.info("%s, running", self.plan[0][0])
            subprocess.call(self.plan[0][0], shell=True)
            logging.info("%s, complete", self.plan[0][0])
            task(self.plan[0][1])
        begin()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-g", "--graph", action='store_true')
    #parser.add_argument("-l", "--log", action='store_true')
    parser.add_argument("plan", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.plan:
        current_worker = worker(args.plan[0])
        if args.graph:
            current_worker.graph()
        else:
            current_worker.run()
