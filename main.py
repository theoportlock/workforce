#!/usr/bin/env python3
import argparse
import subprocess
import pandas as pd
import importlib as il
from pathlib import Path

class run:
    def __init__(self,functionsdir,schema,output):

        print("loading schema...")
        self.schema = pd.read_csv(schema)
        print(self.schema)
        print("done\n")

        print("loading schema functions")
        dfcheck = self.schema["source"].append(self.schema["target"],ignore_index=True).unique()
        print(dfcheck)
        print("done\n")

        print("loding available functions...")
        functions = subprocess.check_output(['ls',functionsdir]).splitlines()
        functions = [i.decode() for i in functions]
        print(functions)
        print("done\n")

        print("checking that schema functions are available...")
        for i in dfcheck:
            if i not in functions:
                print("function " + i + " not found")
                quit()
        print("done\n")

        self.schema["source"] = [functionsdir + "/" + i for i in self.schema["source"]]
        self.schema["target"] = [functionsdir + "/" + i for i in self.schema["target"]]
        self.curr=[]

        print("creating output file..."
        Path(output).mkdir(parents=True, exist_ok=True)
        print("done\n")

        print("init complete\n")

    def task(function):
        
        

    def excecute(self):

        print("begin excecution")
        schema = self.schema

        # start run with first row of schema
        print(schema.iloc[0]["source"]) 
        subprocess.run(schema.iloc[0]["source"])
        self.curr = schema.iloc[0]["target"]

        while self.curr in schema["source"]:
            for i in schema.loc[schema["source"] == self.curr].index:
                self.currloc=schema.iloc[i]["target"] 
                subprocess.run(self.currloc)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--functionsdir')
    parser.add_argument('-s', '--schema')
    parser.add_argument('-o', '--output')
    args = parser.parse_args()
    currentrun = run(args.functionsdir,args.schema,args.output)
    currentrun.excecute()
