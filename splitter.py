#!/usr/bin/env python

import IO
import tester

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
    run = tester.run(f=a,i=IO.bitarrin,d=IO.bitarrdec,o=IO.printerout)
    run.excecute()
