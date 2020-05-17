#!/usr/bin/env python3

import numpy as np

def a(arr,nam):
    with open(nam,"w+") as of:
        of.write("".join(map(str, (arr))))

'''
if __name__ == "__main__":
    print("bitarrin start")
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input')
    args = parser.parse_args()
    print("bitarrin done")
'''
