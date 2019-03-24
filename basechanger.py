'''
### 4. basechanger
* Inputs a single bitarray
* Interprets the bitarray as a binary number
* Returns a unary conversion of the total value of the binary number with trailing 0's equal to the total possible length of the maximum conversion (total unary length = 2^(total binary length))
This function was to initially increase the sparcity of 1's within a bitarray. However, progress remains to be made in the combinations of bits to apply this function to in a bitarray datastream. For instance, if this function was applied to the full length of the bitarray datastream then the 
import tester as t
'''

def a(arr):
    pos = 0
    counter = -1
    conv = [0]*(2**len(arr)-1)
    for e in arr:
        if e:
            counter = counter + 2**pos
        pos += 1
    for f in range(len(conv)):
        conv[f] = 0
    if counter > -1:
        conv[counter] = 1
    return conv

if __name__ == "__main__":
  print(t.bitarrout(a(t.bitarrin())))
