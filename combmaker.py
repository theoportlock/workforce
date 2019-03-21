import arraycompare
import tester
import combadder

def a(arr,x):
    startingarr = [0]*len(arr)

    for i in range(x):
        startingarr[i]=1
    out = []
    currarr = startingarr
    endarr = startingarr[::-1]
    out.append(list(currarr))

    while arraycompare.a(currarr,endarr)==0:
        currarr = combadder.a(currarr)
        out.append(list(currarr))
    return out

if __name__ == "__main__":
    print(a(tester.bitarrin(),tester.decin()))
