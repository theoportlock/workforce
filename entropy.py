def differences(arr):
  output = []
  for a in range(1,len(arr)):
    for b in range(len(arr)-a):
      if arr[b] == arr[b+a]:
	output.append(0)
      else:
	output.append(1)
  return output

test = [1,0,0,0,1,1,1,1,0,0,0,0,1,1,1,1,0,0,0,0,1,1,1,1,0,0,0,1]

for a in range(len(test)):
  test = differences(test)
  print(test)