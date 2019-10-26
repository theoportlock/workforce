import sys
import importlib as il
import os
import inspect

class run:
    def __init__(self, f):
        # read configuration files
        self.f = f
        conffile = "config/"+os.path.basename(sys.argv[0])+"conf"
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

        # load IO file
        IO = variables["IO"]
        if IO == "":
            print("no IO found")
            quit()

        del variables["IO"]

        # find functions in IO
        for j in variables:
            print("loading "+variables[j],"as "+j+" with type:",type(variables[j]))
            variables[j]=IO+"."+variables[j]
            il.import_module(variables[j])
            #k=enum(variables[j]+".a()")
            #variables[j]=enum(variables[j]+".a()")

        #load variables
        self.__dict__.update(variables)
        #print("all modules =",list(sys.modules))
        #print("imported dictionary =",self.__dict__)
        for k in inspect.getmembers(self):
            print(k)
        #print(inspect.getmembers(self))
        print(IO.bitarrin.a())
        self.r=[]
        self.log=[]

    def excecute(self):
        #inputs
        #if callable(self.i):
        #self.i = self.i()

        #if not self.i:
        #    print("no inputs given")
        #    exit()

        #functions
        '''
        self.r = self.f(self.i)
        if self.d:
            self.r = self.d(self.r)

        #output
        if self.o:
            self.o(self.r)

        try:
            variables[j]=variables[j]+".a"
        except KeyError:
            raise ValueError("invalid input")
        '''
