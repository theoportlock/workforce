def a(arr,count=0):
  if arr[count] == 0:
    arr[count] = 1
    return arr
  else:
    arr[count] = 0
    if count+1 == len(arr):
      arr.append(0)
    return a(arr,count+1)

if __name__ == "__main__":
  test = [0]
  for b in range(5):
      test = a(test)
      print(test)