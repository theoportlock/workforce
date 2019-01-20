def a(txt):
  def binadd(arr,count):
    if arr[count] == 0:
      arr[count] = 1
      return arr
    else:
      arr[count] = 0
      return binadd(arr,count+1)
  
  qry = [1]
  comb = [0]*(2**len(txt)-1)
  print("is this read")
  for i, iitem in enumerate(comb):
    print("how bout this")
    for j, jitem in enumerate(qry):
      if qry[j]:
        print("qry is 1")
        if txt[j]:
          comb[i] = 1
          print(comb)
        else:
          comb[i] = 0
          print(comb)
          next
    print("ever get here before adding?")
    qry = binadd(qry,0)
  return comb
'''
  else:
    for k, kitem in enumerate(qry):
      if kitem:
        if txt[k]:
          comb[-1] = 1
          print
        else:
          comb[-1] = 0
          break

  return comb
'''
if __name__ == "__main__":
  text = [1]
  comb = a(text)
  print("final equals")
  print(comb)
