#!/usr/bin/env python3
'''
                    _     __
__      _____  _ __| | __/ _| ___  _ __ ___ ___
\ \ /\ / / _ \| '__| |/ / |_ / _ \| '__/ __/ _ \
 \ V  V / (_) | |  |   <|  _| (_) | | | (_|  __/
  \_/\_/ \___/|_|  |_|\_\_|  \___/|_|  \___\___|


A method for running bash processes in parallel according to a csv file plan

'''
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
        # Setup logging
        self.init_time = str(time())
        logging.basicConfig(filename=str(Path.home())+"/workforce/log.csv", filemode="a", format="%(created).6f,"+self.init_time+","+str(os.getpid())+",%(processName)s,%(message)s", level=logging.INFO)
        logging.info("start %s", plan_file)

        # Load plan
        logging.info("loading plan")
        self.plan_file = plan_file
        self.plan = list(csv.reader(open(self.plan_file), skipinitialspace=True))
        logging.info("plan loaded")

    def run(self):
        # Run loaded plan beginning from the first row
        def begin():
            def task(curr):
                logging.info("running %s", curr)
                subprocess.call(curr, shell=True)
                for i in [k[1] for k in self.plan if k[0] == curr]:
                    Process(target=task, args=[i]).start()
            logging.info("running %s", self.plan[0][0])
            subprocess.call(self.plan[0][0], shell=True)
            task(self.plan[0][1])
        logging.info("begin work")
        begin()
        logging.info("work complete")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.plan:
        current_worker = worker(args.plan[0])
        current_worker.run()
