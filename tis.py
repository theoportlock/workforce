#!/usr/bin/env python

import splitter
import combinations
import addnewelement
import tester as t

def a(arr):
    base = [0]*16
    out = []
    for c in arr:
        base = addnewelement.a(base,[c])
        out.append(combinations.a(splitter.a(base)))
    return out

if __name__ == "__main__":
    job = io.job(a)
    job.i = io.bitarrin()
    job.o = io.plotterout(io.elementnumberout())
    job.run

    for j in result:
        t.plotterout(t.elementnumberout(j))
