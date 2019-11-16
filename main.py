import sys
import importlib as il
import os

class run:
    def __init__(self, f):
        # read configuration files
        self.f = f
        conffile = "tester/config/"+os.path.basename(sys.argv[0])+"conf"
        variables = []
        fvariables = []
        if os.path.exists(conffile):
            with open(conffile) as cf:
                variables = str.splitlines(cf.read())
                for i in variables:
                    fvariables.append(i.split("="))
        else:
            print("no conf file")
            quit()

        variables = {k[0]: k[1] for k in fvariables}

        # find functions in IO
        for j in variables:
            variables[j]="tester.IO." + variables[j]
            print("loading "+variables[j], "as",j)
            try:
                variables[j] = il.import_module(variables[j])
            except ImportError:
                print("no IO function for", j)
                quit()
            try:
                variables[j]=variables[j].a
            except AttributeError:
                print("no function called \"a\" in", j)
                quit()

        #load variables
        self.__dict__.update(variables)
        self.r=[]
        self.log=[]

    def excecute(self):
        if not self.i:
            print("no inputs given")
            quit()

        if not self.o:
            print("no output given")
            quit()

        #functions
        self.r = self.f(self.i())
        if self.d:
            self.r = self.d(self.r)

        #output
        if self.o:
            self.o(self.r)
