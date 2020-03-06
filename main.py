#!/usr/bin/env python3
import logging
import sys
import argparse
import subprocess
import pandas as pd
import importlib as il
from pathlib import Path

class run:
    def __init__(self,functionsdir,schema,output):

        Path(output).mkdir(parents=True, exist_ok=True)

        format = "%(asctime)s: %(message)s"
        logging.basicConfig(format=format, level=logging.INFO, datefmt="%H:%M:%S")
        #logger = logging.getLogger()
        #logger.addHandler(logging.FileHandler(output+"/output.log", 'a'))

        logging.info("loading %s", schema)
        self.schema = pd.read_csv(schema)
        print(self.schema, "\n")
        logging.info("done")

        logging.info("loading schema functions")
        dfcheck = self.schema["source"].append(self.schema["target"],ignore_index=True).unique()
        print(dfcheck, "\n")
        logging.info("done")

        logging.info("loding available functions...")
        functions = subprocess.check_output(['ls',functionsdir]).splitlines()
        functions = [i.decode() for i in functions]
        print(functions, "\n")
        logging.info("done")

        logging.info("checking that schema functions are available...")
        for i in dfcheck:
            if i not in functions:
                logging.info("function " + i + " not found")
                quit()
        logging.info("done")

        self.schema["source"] = [functionsdir + "/" + i for i in self.schema["source"]]
        self.schema["target"] = [functionsdir + "/" + i for i in self.schema["target"]]
        self.curr=[]

        logging.info("init complete")

        
    def excecute(self):

        def task(curr):
            logging.info("running %s",curr) 
            for i in self.schema.loc[self.schema["source"] == curr].index:
                task(self.schema.iloc[i]["target"])
                #subprocess.run(self.currloc)

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
