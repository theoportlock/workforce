#!/usr/bin/env python

import tester.main as t

def a(arr):
    def pairfinder(num):
        return [n-1 for n in range(1, len(num)) if bin(n)[2:].count("1")==2]

    search = pairfinder(arr)
    out = []

    for i in search:
        out.append(arr[i])
    return out

if __name__ == "__main__":
    run = t.run(a)
    run.excecute()
