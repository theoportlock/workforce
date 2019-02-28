import tester as t
import binadder

def a(txt):
  qry = [0]*len(txt)
  comb = [0]*(2**len(txt)-1)
  
  for i, iitem in enumerate(comb[:-1]):
    for j, jitem in enumerate(qry):
      if qry[j]:
        if txt[j]:
          comb[i] = 1
        else:
          comb[i] = 0
          break
    qry = binadder.a(qry,0)
  else:
    for k, kitem in enumerate(qry):
      if kitem:
        if txt[k]:
          comb[-1] = 1
        else:
          comb[-1] = 0
          break

  return comb

if __name__ == "__main__":
    print(t.bitarrout(a(t.bitarrin())))
