def splitter(inarr, outarr):
  for a in range(1,len(inarr)):
    outarr[a-1] = 0
    for b in range(len(inarr)-a):
      if inarr[b] == inarr[b+a] and inarr[b] == 1:
	outarr[a-1] = 1
  return outarr

inp = [0,1,0,0,1,0,1]
outp = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
print(splitter(inp,outp))