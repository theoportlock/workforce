import binadder

def a(arr):
  curr = []
  for i in range(len(arr)-1):
    for j in range(1,len(arr)-i):
      if arr[i] == arr[i+j]:
        curr.append(1)
      else:
        curr.append(0)
  return curr

if __name__ == "__main__":
  test = [1,1,0,0,1]
  print(a(test))
