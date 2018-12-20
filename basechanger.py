'''
Input = 1D bit array of length n
Output = 1D bitarray of length (2^n)-1 with 1 active bit if there are more than one active bits in the input
'''
def basechanger(arr):
  pos = 0
  counter = -1
  conv = [0]*(2**len(arr)-1)
  for e in arr:
    if e == 1:
      counter = counter + 2**pos
    pos += 1
  for f in range(len(conv)):
    conv[f] = 0
  if counter > -1:
    conv[counter] = 1
  return conv

'''
text = [1,1]
print(basechanger(text))
'''