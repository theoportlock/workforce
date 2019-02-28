import tester1 as t

def a(arr):
  output = []
  for a in arr:
    for b in range(a-1):
      output.append(0)
    output.append(1)
  return output

if __name__ == "__main__":
    print(a(t.decarrin()))
