text = [0,1,1,1,1,0,0,1,0,0,1,0,1,1,1,1,1,0]
nerv = [0]*10
newnerv = [0]*30

def basechanger(nrv,base):
  pos = 0
  counter = -1
  conv = [0]*((base**2)-1)
  for e in range(len(nrv)-1,len(nrv)-base-1,-1):
    if nrv[e] == 1:
      counter = counter + 2**pos
    pos += 1
  for f in range(len(conv)):
    conv[f] = 0
  if counter > 0:
    conv[counter] = 1
  return conv


for c in text:
  for d in range(len(nerv)-1,0,-1):
    nerv[d] = nerv[d-1]
  nerv[0] = c
  tmp = basechanger(nerv,2)
  for e in tmp:
    for g in range(len(newnerv)-1,0,-1):
      newnerv[g] = newnerv[g-1]
    newnerv[0] = e
    print newnerv
