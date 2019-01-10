import math
import numpy as np

def nCr(n,r):
    f = math.factorial
    return f(n) / f(r) / f(n-r)

def initadd(arr):
  x,y=0,1
  return add(x,y,arr)

def add(x,y,tmp):
  if tmp[x]==1:
      if tmp[x]==tmp[x+1]:
	  y+=1
	  tmp[y-2],tmp[x]=tmp[x],tmp[y-2]
	  add(x+1,y,tmp)
      else:
	tmp[x],tmp[x+1]=tmp[x+1],tmp[x]
	#print("tmp: {0} \nx: {1} \ny: {2}".format(tmp,x,y))
  else:
      add(x+1,y,tmp)
  return tmp

text=[0,1,0,0,1,0]

#make array
for a in range(1,len(text)+1):
  replace = np.zeros([len(text),252])

#for each pair/tripple  
for i in range(2,len(replace[...])+2):
  print("i= {0}".format(i))
  for j in range(i):
    replace[i-2][j]=1
  print(replace)
  #print("replace=\n{0}".format(replace)
  #loop through all combinations
  """
  for l in xrange(nCr(len(replace),i)):
    replace = initadd(replace)
    print (replace)
  """