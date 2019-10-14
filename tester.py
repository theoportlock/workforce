import sys
import os

class run:
    #need to sort this out
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.r=[]
        self.log=[]
        print(os.path.basename(sys.argv[0]))

    def excecute(self):
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
