#!/usr/bin/env python

import tester.main as t

import numpy as np

def a(arr):
    output = np.fft.fft(arr)
    return output

if __name__ == "__main__":
    run = t.run(a)
    run.excecute()
