def packer(arr):
  output = []
  for a, b in enumerate(arr):
    if b == 1:
      output.append(a)
  return output

test = [0,1,0,0,0,1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,1]

print (packer(test))