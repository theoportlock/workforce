def a(arr):
  output = []
  for a in arr:
    print(a)
    for b in range(a-1):
      output.append(0)
    output.append(1)
  return output

if __name__ == "__main__":
  test = [12,3,1]
  print(a(test))
