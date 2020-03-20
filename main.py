#!/usr/bin/env python3
import logging
import multiprocessing
#import threading
import argparse
import subprocess
import pandas as pd
import importlib as il
from pathlib import Path

class run:
    def __init__(self,functionsdir,schema,output):
        format = "%(asctime)s %(processName)s: %(message)s"
        logging.basicConfig(format=format, level=logging.INFO, datefmt="%H:%M:%S")

        if output:
            Path(output).mkdir(parents=True, exist_ok=True)
            logger = logging.getLogger()
            logger.addHandler(logging.FileHandler(output+"/output.log", 'a'))

        if not schema:
            logging.error("no schema loaded (use -s flag)")
            quit()
        else:
            logging.info("loading %s", schema)
            self.schema = pd.read_csv(schema)
            print(self.schema, "\n")
            logging.info("done")
            
        if functionsdir:
            logging.info("loading functions in supplied directory")
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
        processes = []
        def task(curr):
            logging.info("running %s",curr) 
            multiprocessing.active_children()
            subprocess.run(curr,shell=True)
            targets = self.schema.loc[self.schema["source"] == curr].index
            for j in targets:
                print("j={}".format(j))
                if j == 0:
                    task(self.schema.iloc[j]["target"])
                else:
                    #t=threading.Thread(target=task, args=[self.schema.iloc[i]["target"]])
                    t = multiprocessing.Process(target=task, args=(self.schema.iloc[j]["target"],))
                    t.start()

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
