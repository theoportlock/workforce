def a(arr):
  output = []
  for a in range(1,len(arr)):
    curr = 0
    for b in range(len(arr)-a):
      if arr[b] == arr[b+a] and arr[b] == 1:
        curr = 1
    output.append(curr)
  return output

if __name__ == "__main__":
  inp = [0,0,1,0,0,1,1,0,0]
  print(a(inp))
