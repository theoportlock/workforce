def a(inp):
  with open(inp) as tf:
    return list(map(int,''.join(format(ord(x),'b') for x in tf.read())))

if __name__  == "__main__":
  test = a("input.txt")
  print(test)
