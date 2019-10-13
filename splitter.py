#!/usr/bin/env python

import io

class run:
    def __init__(self,function):
        self.function=function
        self.i=[]
        self.o=[]
        self.log=[]

    def excecute(self):
        self.o(self.function(self.i))

def a(arr):
    output = []
    for a in range(1,len(arr)):
        curr = 0
        for b in range(len(arr)-a):
            if arr[b] and arr[b+a]:
                curr = 1
        output.append(curr)
    return output

if __name__ == "__main__":
    run = run(a)
    print(io.bitarrout(io.bitarrin()))
    #run.i = io.bitarrin()
    #run.o = io.bitarrout()
    #run.excecute()
