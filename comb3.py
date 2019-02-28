import tester as t
import packer
import binadder
import basechanger

def a(arr):
  tmp = [0]*len(packer.a(arr))
  packed = packer.a(arr)
  comb = []

  for a in range(2**len(tmp)-1):
    tmp = binadder.a(tmp)
    curr = 0
    for b,c in enumerate(tmp):
      if c == 1:
        curr = curr + packed[b]
    comb.append(curr)
  out = []
  for d in comb:
      for e in basechanger.a(list(map(int,"{0:#b}".format(d)[2:]))):
          out.append(e)
  return out

if __name__ == "__main__":
  print(t.bitarrout(a(t.bitarrin())))
