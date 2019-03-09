# attempting to use multidimensional input for basechanger interaction

import tester as t

def a(arr):
    def reducer(currarr):
        for elements in currarr:
            output = []
            for a in range(1,len(currarr)):
                curr = 0
                for b in range(len(currarr)-a):
                    if not arr[b] == arr[b+a]:
                        curr = 1
                output.append(reducer(elements))
        return output
    return output

if __name__ == "__main__":
    print(a(t.multibitarrin()))
