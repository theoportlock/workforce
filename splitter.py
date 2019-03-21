import tester as t

def a(arr):
    output = []
    for a in range(len(arr)):
        curr = 0
        for b in range(len(arr)-a):
            if arr[b] and arr[b+a]:
                curr = 1
        output.append(curr)
    return output

if __name__ == "__main__":
    arr1 = t.bitarrin()
    print(t.bitarrout(a(arr1)))
    '''
    for j in range(10):
        arr1 = a(arr1)
        print(t.bitarrout(arr1))
        print(t.bitarrstats(arr1))
    '''
    
