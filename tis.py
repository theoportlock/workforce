import splitter
import basechanger
import comb
import addnewelement
import tester as t

def a(arr):
    nerv = [0]*2
    newnerv = [0]*8
    out = []
    for c in arr:
      for e in basechanger.a(addnewelement.a(nerv,list(map(int,list(str(c)))))):
        out.append(comb.a(splitter.a(addnewelement.a(newnerv,list(map(int,list(str(c))))))))
    return out
 
if __name__ == "__main__":
    print(t.bitarrout(a(t.bitarrin())))
