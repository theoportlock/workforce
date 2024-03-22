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
            self.plan = list(csv.reader(csvfile, delimiter="\t", skipinitialspace=True))

    def run(self):
        # Run loaded plan beginning from the first row
        self.init_time = str(time())
        logging.basicConfig(
                filename=str(Path.cwd())+"/wflog.csv",
                filemode="w",
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
