def a(arr,inp):
  for d in range(len(arr)-1,0,-1):
    arr[d] = arr[d-1]
  arr[0] = inp
  return arr

if __name__ == "__main__":
  test = [0,0,1,0,0,1]
  numb = 1
  print("test =")
  print(test)
  print("add the number")
  print(numb)
  print("results in")
  print(a(test,numb))
