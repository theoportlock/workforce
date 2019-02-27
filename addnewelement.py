import tester

def a(arr,inp):
    for b in inp:
      for d in range(len(arr)-1,0,-1):
        arr[d] = arr[d-1]
      arr[0] = b 
    return arr

if __name__ == "__main__":
    print(tester.twotest(a))
    print(list(1))
