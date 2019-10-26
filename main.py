#!/usr/bin/env python

import tester.main as t

import splitter
import combinations
import addnewelement

def a(arr):
    base = [0]*16
    out = []
    for c in arr:
        base = addnewelement.a([base,[c]])
        out.append(combinations.a(splitter.a(base)))
    return out

if __name__ == "__main__":
    run = t.run(a)
    run.excecute()
