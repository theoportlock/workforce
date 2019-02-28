import tester as t

def a(arr1,arr2):
    if len(arr1) != len(arr2):
        return 0
    else:
        for a,b in enumerate(arr1):
            if b != arr2[a]:
                return 0
    return 1 


if __name__ == "__main__":
    print(a(t.bitarrin(),t.bitarrin()))
