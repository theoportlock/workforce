#!/usr/bin/env python3
import logging
import multiprocessing
import sys
import argparse
import subprocess
import pandas as pd
import importlib as il
from pathlib import Path

class run:
    def __init__(self,functionsdir,schema,output):
        # functionsdir -- directory of functions
        # functions -- functions in directory of functions
        # self.schema -- pandas csv of schema file

        format = "%(asctime)s %(processName)s %(threadName)s: %(message)s"
        logging.basicConfig(format=format, level=logging.INFO, datefmt="%H:%M:%S")

        # create output directory if one is necessary
        if output:
            Path(output).mkdir(parents=True, exist_ok=True)
            logger = logging.getLogger()
            logger.addHandler(logging.FileHandler(output+"/output.log", 'a'))

        logging.info("loading %s", schema)
        self.schema = pd.read_csv(schema)
        print(self.schema, "\n")
        logging.info("done")

        if functionsdir:
            logging.info("loding available functions")
            functions = subprocess.check_output(['ls',functionsdir]).splitlines()
            functions = [i.decode() for i in functions]
            print(functions, "\n")
            logging.info("done")
        else:
            functions = []

        logging.info("checking that schema functions are available")
        for i in self.schema.index:
            for j in ("source","target"):
                if self.schema[j][i] not in functions:
                    logging.warning("function " + self.schema[j][i] + " not found")
                else:
                    logging.info("function " + self.schema[j][i] + " found")
                    self.schema.loc[i,j] = functionsdir + "/" + self.schema[j][i]
        print(self.schema)
        logging.info("done")
        logging.info("init complete")

    def excecute(self):
        def task(curr):
            logging.info("running %s",curr) 
            subprocess.run(curr.split())
            for i in self.schema.loc[self.schema["source"] == curr].index:
                t=multiprocessing.Process(target=task, args=[self.schema.iloc[i]["target"]])
                t.start()
                #task(self.schema.iloc[i]["target"])

        logging.info("begin excecution")
        # start run with first row of schema
        task(self.schema.iloc[0]["source"])

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--functionsdir')
    parser.add_argument('-s', '--schema')
    parser.add_argument('-o', '--output')
    args = parser.parse_args()
    currentrun = run(args.functionsdir,args.schema,args.output)
    currentrun.excecute()
