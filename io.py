import matplotlib.pyplot as plt
import os.path

def bitarrin():
    return list(map(int,input("Input bitarray: ")))

def multibitarrin():
    arr = []
    dimension = int(input("Enter the number of dimensions: "))
    for j in range(dimension):
        subarr = []
        print("For dimension ",j+1)
        number = int(input("Enter the number of elements: "))
        print ('Enter nested bitarray: ')
        for i in range(number):
            print("element ",i+1," =")
            n = list(map(int,input("Input bitarray: ")))
            if number == 1:
                subarr = n
            else:
                subarr.append(n)
        if dimension == 1:
            arr = subarr
        else:
            arr.append(subarr)
    print("inputted array = ",arr)
    return arr   

def filein():
    with open("Input filename: ") as tf:
        return list(map(int,''.join(format(ord(x),'b') for x in tf.read ())))

def decin():
    return int(input("Input decmial: "))

def decarrin():
    decarr = []
    number = input("Enter the number of elements: ")
    print ('Enter numbers in array: ')
    for i in range(int(number)):
        print("element ",i," =")
        n = input("")
        decarr.append(int(n))
    return decarr   

def bitarrout(inputs):
    return "".join(map(str,(inputs)))

def bitarrstatsout(arr):
    def percentactive(arr):
        lcount = 0
        for l in ar:
            if l == 1:
                lcount += 1
        return (float(lcount)/float(len(arr)))*100
    output = ""
    output += "Percentage active equals:\n"
    output += str(percentactive(arr))
    output += "array length equals:\n"
    output += str(len(arr))
    return percentactive(arr)

def elementnumberout(arr): 
  output = []
  for a, b in enumerate(arr):
    if b:
      output.append(a+1)
  return output

def plotterout(arr):
    B = arr[:len(arr)//2]
    C = arr[len(arr)//2:len(arr)-1]
    print("blen= ",len(B),"clen= ",len(C))
    plt.scatter(B,C)

    def nextname(a=1,pre="",ext="",directory="."):
        if os.path.exists(directory+pre+str(a)+ext):
            existancecheck(a+1,pre,ext)
        else:
            return directory+pre+str(a)+ext

    plt.savefig(nextname(ext=".png"))
    existancecheck(a)
