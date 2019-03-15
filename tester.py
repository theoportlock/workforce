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

def bitarrstats(arr):
    def percentactive(ar):
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
