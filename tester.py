import sys
import importlib
import os

#SORT OUT IMPORTLIB
class run:
    def __init__(self):

        #read configuration files
        conffile = "config/"+os.path.basename(sys.argv[0])+"conf"
        variables = []
        fvariables = []
        if os.path.exists(conffile):
            with open(conffile) as cf:
                variables = str.splitlines(cf.read())
                for i in variables:
                    fvariables.append(i.split("="))

        lvariables = {k[0]: k[1] for k in fvariables}
        print(lvariables)

        #find IO and load
        print (lvariables["IO"])
        
        #import lvariables["IO"]

        #find functions in IO
        #for j in lvariables:
        #    j = eval(j)

        #load variables
        #self.__dict__.update(lvariables)

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
