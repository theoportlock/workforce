#!/usr/bin/env python3
import numpy as np
import arr2file
import argparse

def a(arr):
    return np.array(list(map(int,arr)))

if __name__ == "__main__":
    print("bitarrin start")
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output')
    args = parser.parse_args()
    arr2file.a(a(input("Input bitarray ")),args.output)
    print("bitarrin done")
