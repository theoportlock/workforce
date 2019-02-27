import tester

def a(arr,x=0,y=0):
    if arr[x]:
        if arr[x+1]:
            y += 1
            arr[y-1],arr[x] = arr[x],arr[y-1]
            a(arr,x+1,y)
        else:
            arr[x],arr[x+1]=arr[x+1],arr[x]
    else:
        a(arr,x+1,y)
    return arr

if __name__ == "__main__":
    print(tester.test(a))
