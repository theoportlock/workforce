import tester

def a(arr,x=0):
    if arr[x]:
        arr[x]=0
        if arr[x+1]:
            arr[0] = 1
            arr[x+2] = 1
        else:
            arr[x+1]=1
    else:
        a(arr,x+1)
    return arr

if __name__ == "__main__":
    print(tester.test(a))
