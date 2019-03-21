import tester as t

def a(arr):
  output = []
  for a, b in enumerate(arr):
    if b:
      output.append(a+1)
  return output

if __name__ == "__main__":
    print(a(t.bitarrin()))
