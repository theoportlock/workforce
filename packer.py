def a(arr):
  output = []
  for a, b in enumerate(arr):
    if b == 1:
      output.append(a)
  return output

if __name__ == "__main__":
  test = [0,1,0,0,0,1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,1]
  print (a(test))
