def combinations(arr):
  def packer(arr):
    output = []
    for a, b in enumerate(arr):
      if b == 1:
	output.append(2**a)
    return output

  def binadd(arr,count):
    if arr[count] == 0:
      arr[count] = 1
      return arr
    else:
      arr[count] = 0
      return binadd(arr,count+1)

  tmp = [0]*len(packer(arr))
  packed = packer(arr)
  comb = []

  for a in range(2**len(tmp)-1):
    tmp = binadd(tmp,0)
    curr = 0
    for b,c in enumerate(tmp):
      if c == 1:
	curr = curr + packed[b]
    comb.append(curr)

  return comb

test = [0,0]

print(combinations(test))
