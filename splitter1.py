import tester as t

def a(arr):
    output = []
    for a in range(len(arr)):
        dim1 = []
        for b in range(len(arr[a])):
            curr = 0
            for c in range(len(arr)-a):
                for d in range(len(arr[a])-b):
                    #print("c = ",c," d = ",d)
                    #print("a+c = ",a+c," b+d = ",b+d)
                    if a+c <= len(arr) and b+d <= len(arr[a]): 
                        print("a+c = ",a+c," b+d = ",b+d)
                        if arr[c][d] and arr[a+c][b+d]:
                            curr = 1
            dim1.append(curr)
        output.append(dim1)
    return output

if __name__ == "__main__":
    array = [[1,0,0,0],[0,1,0,0,1],[0,0,0,1,0]]
    print(array)
    print(a(array))
    #print(a(t.multibitarrin()))
