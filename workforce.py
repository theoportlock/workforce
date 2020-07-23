#!/usr/bin/env python3
from multiprocessing import Process
from pathlib import Path
from time import time
import argparse
import logging
import csv
import subprocess

class worker:
    ''' A method for running bash processes in parallel according to a csv file plan '''
    def __init__(self, plan_file):
        # Setup logging
        self.init_time = str(time())
        logging.basicConfig(filename=str(Path.home())+"/workforce/log.csv", filemode="a", format="%(created).6f,"+self.init_time+",%(processName)s,%(message)s", level=logging.INFO)
        logging.info("begin %s", plan_file)

        # Load plan
        logging.info("loading plan") 
        self.plan_file = plan_file
        self.plan = list(csv.reader(open(self.plan_file), skipinitialspace=True))
        logging.info("plan loaded")

    def run(self):
        # Run loaded plan beginning from the first row
        def task(curr):
            logging.info("running %s", curr[1]) 
            subprocess.run(curr[1], shell=True)
            for i, j in enumerate(self.plan):
                if j[0] == curr[1]:
                    t = Process(target=task, args=[self.plan[i]])
                    t.start()
        logging.info("begin work")
        logging.info("running %s", self.plan[0][0]) 
        subprocess.run(self.plan[0][0], shell=True)
        task(self.plan[0])
        logging.info("work complete")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.plan:
        current_worker = worker(args.plan[0])
        current_worker.run()
