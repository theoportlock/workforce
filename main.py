#!/usr/bin/env python3
import logging
import multiprocessing
import argparse
import subprocess
import pandas as pd
import importlib as il
from pathlib import Path

class run:
    def __init__(self,functionsdir,schema):
        format = "%(asctime)s %(processName)s: %(message)s"
        logging.basicConfig(format=format, level=logging.INFO, datefmt="%H:%M:%S")
        logger = logging.getLogger()
        logger.addHandler(logging.FileHandler("output.log", 'a'))

        if not schema:
            logging.error("no schema loaded (use -s flag)")
            quit()
        else:
            logging.info("loading %s", schema)
            self.schema = pd.read_csv(schema)
            print(self.schema, "\n")
            logging.info("done")
            
        if functionsdir:
            logging.info("loading functions in supplied directories")
            functions = subprocess.check_output(['ls',functionsdir]).splitlines()
            functions = [i.decode() for i in functions]
            print(functions, "\n")
            
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
        jobs = []
        def task(curr):
            logging.info("running %s",curr) 
            subprocess.run(curr,shell=True)
            for i in self.schema.loc[self.schema["source"] == curr].index:
                t = multiprocessing.Process(target=task, args=[self.schema.iloc[i]["target"]])
                jobs.append(t)
                t.start()
            t.join()

        logging.info("begin excecution")
        # start run with first row of schema
        task(self.schema.iloc[0]["source"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--functionsdir')
    parser.add_argument('-s', '--schema')
    args = parser.parse_args()

    currentrun = run(args.functionsdir,args.schema)
    currentrun.excecute()
