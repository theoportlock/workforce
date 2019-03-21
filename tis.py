import splitter
import basechanger
import comb
import addnewelement
import elementno
import tester as t

def a(arr):
    base = [0]*14
    out = []
    for c in arr:
        base = addnewelement.a(base,[c])
        out.append(comb.a(splitter.a(base)))
    return out
 
if __name__ == "__main__":
    for j in a(t.bitarrin()):
        print(elementno.a(j))
