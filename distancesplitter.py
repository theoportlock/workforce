#Input a text file
#t = raw_input("Input file path: ")
t = "input.txt"

#Separate the bitarray of the text by measuring distances between bits
with open(t) as f:
  text = map(int,''.join(format(ord(x), 'b') for x in f.read()))
  nerv = [0]*50
  node = [0]*(len(nerv)-1)
  for c in text:
    for d in range(len(nerv)-1,0,-1):
      nerv[d] = nerv[d-1]
    nerv[0] = c
    for a in range(1,len(nerv)):
      node[a-1] = 0
      for b in range(len(nerv)-a):
	if nerv[b] == nerv[b+a] and nerv[b] == 1:
	  node[a-1] = 1
    print(node)
