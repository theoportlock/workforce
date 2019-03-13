# supports multidimensional input (all subarrays must be same length for now)

def a(arr):
    output = []
    for a in range(len(arr)):
        dim1 = []
        for b in range(len(arr[a])):
            curr = 0
            for c in range(len(arr)-a):
                for d in range(len(arr[a])-b):
                    if a+c <= len(arr) and b+d <= len(arr[a]): 
                        if arr[c][d] and arr[a+c][b+d]:
                            curr = 1
            dim1.append(curr)
        output.append(dim1)
    return output

if __name__ == "__main__":
    array = [[1,0,0,0,0],[0,1,0,0,1],[0,0,0,1,0]]
    print("input array =")
    print(array)
    print("distances array =")
    print(a(array))
