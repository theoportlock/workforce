def a(arr):
  output = [0]
  for i, j in enumerate(arr):
    if j:
      output[0] += 2**i
  return output

if __name__ == "__main__":
  test = [1,0,1]
  print("test =")
  print(test)
  print("basechanger =")
  print(a(test))
  
