def splitter(inarr, outarr):
  for a in range(1,len(inarr)):
    outarr[a-1] = 0
    for b in range(len(inarr)-a):
      if inarr[b] == inarr[b+a] and inarr[b] == 1:
	outarr[a-1] = 1
  return outarr

def basechanger(arr):
  pos = 0
  counter = -1
  conv = [0]*(2**len(arr)-1)
  for e in arr:
    if e == 1:
      counter = counter + 2**pos
    pos += 1
  for f in range(len(conv)):
    conv[f] = 0
  if counter > -1:
    conv[counter] = 1
  return conv

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

def outreader(arr,out):
  with open(out,"a") as of:
    of.write(str(arr)+"\n")

def inreader(inp):
  with open(inp) as tf:
    return map(int,''.join(format(ord(x), 'b') for x in tf.read()))

def addnewelement(arr,inp):
  for d in range(len(arr)-1,0,-1):
    arr[d] = arr[d-1]
  arr[0] = inp
  return arr

nerv = [0]*2
newnerv = [0]*12
split = [0]*(len(newnerv)-1)
text = inreader("input.txt")

'''
for c in text:
  for e in basechanger(addnewelement(nerv,c)):
    newnerv = addnewelement(newnerv,e)
    split = splitter(newnerv,split)
  outreader(combinations(split),"output.csv")
'''

print ('text = {0}\n'.format(text))
for c in text:
  nerv = addnewelement(nerv,c)
  print ('nerv			{0}'.format(nerv))
  print ('then changed base	{0}'.format(basechanger(nerv)))
  for e in basechanger(nerv):
    newnerv = addnewelement(newnerv,e)
    split = splitter(newnerv,split)
  print ('	newnerv		{0}'.format(newnerv))
  print ('	new split	{0}'.format(split))
  print ('	comb		{0}'.format(combinations(split)))
  print ('\n')