import sys
import importlib as il
import os
import IO.IO

class run:
    def __init__(self, f):
        #read configuration files
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

        import IO.bitarrin

        l = IO.bitarrin.a()
        print(l)

        IO = variables["IO"]
        if IO == "":
            print("no IO found")
            quit()

        del variables["IO"]

        #find functions in IO
        functions = []
        for j in variables:
            print("j =",j)
            print("loading "+variables[j]," with type:",type(variables[j]))
            variables[j]=IO+"."+variables[j]
            il.import_module(variables[j])
            try:
                variables[j]=variables[j]+".a"
            except KeyError:
                raise ValueError("invalid input")

        IO.printerout.a()
        print(variables)
        print(IO)

        #load variables
        #self.__dict__.update(functions)
        self.r=[]
        self.log=[]

    def excecute(self):
        '''
        #inputs
        if callable(self.i):
            self.i = self.i()

        if not self.i:
            print("no inputs given")
            exit()

        #functions
        self.r = self.f(self.i)
        if self.d:
            self.r = self.d(self.r)

        #output
        #for i in self.o*

        #not sure here
        if self.o:
            self.o(self.r)
        '''
