#!/usr/bin/env python3

def a(file):
    with open(file) as tf:
        return list(map(int,''.join(format(ord(x),'b') for x in tf.read ())))

if __name__ == "__main__":
    print(a(input("Input filename ")))
