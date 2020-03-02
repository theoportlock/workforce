#!/usr/bin/env python3
import argparse
import subprocess
import pandas as pd
import importlib as il

class run:
    def __init__(self,functionsdir,schema):

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

        print("init complete\n")

    def excecute(self):
        print("begin excecution")
        schema = self.schema
        print(schema)
        # start run with first row of schema
        print(schema.iloc[0]["source"] + " --> " + schema.iloc[0]["target"])
        subprocess.run(schema.iloc[0]["source"])
        subprocess.run(schema.iloc[0]["target"])
        self.curr = schema.iloc[0]["target"]
        print(self.curr)
        '''

        while self.curr in schema["source"]:
            for i in schema.loc[schema["source"]==self.currloc].index:
                print(self.funcnames[schema.iloc[i]["source"]] + " --> " + self.funcnames[schema.iloc[i]["target"]])
                self.currval=functions[schema.iloc[i]["target"]](functions[schema.iloc[i]["source"]](self.currval))
                print(self.currval)
                self.currloc=schema.iloc[i]["target"] 
                '''

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--functionsdir')
    parser.add_argument('-s', '--schema')
    args = parser.parse_args()
    currentrun = run(args.functionsdir,args.schema)
    currentrun.excecute()
