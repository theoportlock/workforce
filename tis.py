def splitter(inarr, outarr):
  for a in range(1,len(inarr)):
    outarr[a-1] = 0
    for b in range(len(inarr)-a):
      if inarr[b] == inarr[b+a] and inarr[b] == 1:
	outarr[a-1] = 1
  return outarr

def basechanger(arr,base):
  pos = 0
  counter = -1
  conv = [0]*((base**2)-1)
  for e in range(len(arr)-1,len(arr)-base-1,-1):
    if arr[e] == 1:
      counter = counter + 2**pos
    pos += 1
  for f in range(len(conv)):
    conv[f] = 0
  if counter > 0:
    conv[counter] = 1
  return conv

def combinations(arr):
# Defining a function that adds one to a previous binary string
  def binadd(arr,count):
    if arr[count] == 0:
      arr[count] = 1
      return arr
    else:
      arr[count] = 0
      return binadd(arr,count+1)
# Create arrays (will have to fix to make a continuous process)
  qry = [0]*len(arr)
  comb = [0]*2**len(arr)
# certain this section can be written better  
  for i, iitem in enumerate(comb[:-1]):
    for j, jitem in enumerate(qry):
      if qry[j] == 1:
	if arr[j] == 1:
	  comb[i] = 1
	else:
	  comb[i] = 0
	  break
    qry = binadd(qry,0)
  else:
    for k, kitem in enumerate(qry):
      if kitem == 1:
	if arr[k] == 1:
	  comb[-1] = 1
	else:
	  comb[-1] = 0
	  break
  return comb

def outreader(out,arr):
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

nerv = [0]*8
newnerv = [0]*10
node = [0]*(len(newnerv)-1)
text = inreader("input.txt")

for c in text:
  for e in basechanger(addnewelement(nerv,c),2):
    newnerv = addnewelement(newnerv,e)
    node = splitter(newnerv,node)
  outreader("output.csv",combinations(node))

