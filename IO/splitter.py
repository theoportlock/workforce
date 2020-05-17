#!/usr/bin/env python
import file2arr
import arr2file
import argparse

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
    print("splitter start")
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input')
    parser.add_argument('-o', '--output')
    args = parser.parse_args()
    arr2file.a(a(file2arr.a(args.input)),args.output)
    print("splitter done")
