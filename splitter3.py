import tester as t
import binadder
import combmaker

def a(arr):
    out = []
    qryarr = combmaker(arr,a)
    for j in qryarr
        matches = 1
        for i in range(len(j)):
            if qry[i] and not arr[i]:
                matches = 0
        out.append(matches)
    return out

if __name__ == "__main__":
    with open("output.txt","a") as of:
        of.write(t.bitarrout(a(t.bitarrin())))
