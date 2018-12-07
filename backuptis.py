# 1. Defining how all combinations work
def combinations(txt):
# Defining a function that adds one to a previous binary string
  def binadd(arr,count):
    if arr[count] == 0:
      arr[count] = 1
      return arr
    else:
      arr[count] = 0
      return binadd(arr,count+1)

# Create arrays (will have to fix to make a continuous process)
  qry = [0]*len(txt)
  comb = [0]*2**len(txt)
# certain this section can be written better  
  for i, iitem in enumerate(comb[:-1]):
    for j, jitem in enumerate(qry):
      if qry[j] == 1:
	if txt[j] == 1:
	  comb[i] = 1
	else:
	  comb[i] = 0
	  break
    qry = binadd(qry,0)
  else:
    for k, kitem in enumerate(qry):
      if kitem == 1:
	if txt[k] == 1:
	  comb[-1] = 1
	else:
	  comb[-1] = 0
	  break
  return comb


#2. Reading the "input.txt" file as bitarray
t = "input.txt"
o = "output.txt"
with open(o,"a") as of:
  with open(t) as tf:
    text = map(int,''.join(format(ord(x), 'b') for x in tf.read()))

#3. Make sparce - sampling rate effects resolution (maybe have multiple sampling rates)

#4. Find combinations    
# Nerv length should be refined (don't know how yet) - linked to sampling rate
    nerv = [0]*8
    node = [0]*(len(nerv)-1)
# For every bin in each letter, separate the bitarray of the text by measuring distances between bits
    for c in text:
      for d in range(len(nerv)-1,0,-1):
	nerv[d] = nerv[d-1]
      nerv[0] = c
      for a in range(1,len(nerv)):
	node[a-1] = 0
	for b in range(len(nerv)-a):
	  if nerv[b] == nerv[b+a] and nerv[b] == 1:
	    node[a-1] = 1
#5. Verify by output
      of.write(str(combinations(node))+"\n")

