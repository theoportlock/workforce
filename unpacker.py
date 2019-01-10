def unpacker(arr):
  output = []
  for a in arr:
    print a
    for b in range(a-1):
      output.append(0)
    output.append(1)
  return output

test = [12,3,1]
print unpacker(test)