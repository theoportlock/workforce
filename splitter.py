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
    print(t.bitarrout(a(t.bitarrin())))
