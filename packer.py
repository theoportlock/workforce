import tester

def a(arr):
  output = []
  for a, b in enumerate(arr):
    if b:
      output.append(2**a)
  return output

if __name__ == "__main__":
    print(tester.test(a))
