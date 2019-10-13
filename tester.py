class run:
    #need to sort this out
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.r=[]
        self.log=[]

    def excecute(self):

        if callable(self.i):
            self.i = self.i()

        if not self.i:
            print("no inputs given")
            exit()

        self.r = self.f(self.i)

        if self.d:
            self.r = self.d(self.r)

        if self.o:
            self.o(self.r)
