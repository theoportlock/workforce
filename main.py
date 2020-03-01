import argparse
import pandas as pd
import importlib as il
class cursor:
    def __init__(self):


class run:
    def __init__(self,functions,schema):

        print("loading schema...")
        df = pd.read_csv(schema)
        print(df)
        print("schema loaded successfully\n")

        self.schema = df

        print("loading functions...")
        with open(functions) as f:
            functions = str.splitlines(f.read())
            print(functions)
            self.funcnames = functions[:]

        for j,k in enumerate(functions):
            functions[j]="IO." + k
            print("loading "+str(j)+" "+k)
            try:
                functions[j] = il.import_module(functions[j])
            except ImportError:
                print("MISSING FUNCTION")
                quit()
            print("LOADED")
            try:
                functions[j]=functions[j].a
            except AttributeError:
                print("no function called \"a\" in", j)
                quit()

        self.__dict__.update(enumerate(functions))
        self.currloc=[]
        self.currval=[]
        print("complete\n")

    def excecute(self):
        print("begin excecution")
        df = self.schema
        functions = self.__dict__ 

        # start run with first row of schema
        print(self.funcnames[df.iloc[0]["source"]] + " --> " + self.funcnames[df.iloc[0]["target"]])
        self.currval=functions[df.iloc[0]["target"]](functions[df.iloc[0]["source"]]())
        self.currloc=df.iloc[0]["target"]

        while self.currloc in df["source"]:
            for i in df.loc[df["source"]==self.currloc].index:
                print(self.funcnames[df.iloc[i]["source"]] + " --> " + self.funcnames[df.iloc[i]["target"]])
                self.currval=functions[df.iloc[i]["target"]](functions[df.iloc[i]["source"]](self.currval))
                print(self.currval)
                self.currloc=df.iloc[i]["target"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--functions')
    parser.add_argument('-s', '--schema')
    args = parser.parse_args()
    currentrun = run(args.functions,args.schema)
    currentrun.excecute()
