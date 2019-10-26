#!/usr/bin/env python

import tester

def a(arr):
    out = [] 
    for b in arr[1]:
        for c in range(len(arr[0])-1,0,-1):
            arr[0][c] = arr[0][c-1]
            arr[0][0] = b 
    return arr[0]

if __name__ == "__main__":
    run = tester.run(a)
    run.excecute()
