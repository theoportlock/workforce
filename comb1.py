import math
import tester
import numpy as np

def a(arr):
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
    else:
        add(x+1,y,tmp)
    return tmp

  #make array
  for a in range(1,len(arr)+1):
    replace = np.zeros([len(arr),252])

  #for each pair/tripple  
  for i in range(2,len(replace[...])+2):
    for j in range(i):
      replace[i-2][j]=1

if __name__ == "__main__":
  tester.test(a)
