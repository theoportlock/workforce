import packer
import binadder

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
  return comb

if __name__ == "__main__":
  test = [1,1,1,1,1]
  print(test)
  print(a(test))
