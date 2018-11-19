with open("temp.txt") as f:
  text = map(int,''.join(format(ord(x), 'b') for x in f.read()))	#input text
  print(text)
  nerv = [0]*20 							#create an empty nerv of any size
  node = [0]*(len(nerv)-1) 						#create nodes that look at distances between nerv cells that sould be one less than nerv
  for c in text: 							#for each letter in the input text
    for d in range(len(nerv)-1,0,-1): 					#shuffle the nerv cells to prepare for the new binary
      nerv[d] = nerv[d-1]
      nerv[0] = c 							#add new binary from input text
      for a in range(1,len(nerv)): 					#gap incrimentation increase starting at 1
	node[a-1] = 0 							#reset current gap incrimentation to be 0
	for b in range(len(nerv)-a): 					#search nerv for a gap matching the current size
	  if nerv[b] == nerv[b+a] and nerv[b] == 1: 			#if found then:
	    node[a-1] = 1 						#activate the corresponding node
    print (node)