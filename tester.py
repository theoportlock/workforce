def bitarrin():
    return list(map(int,input("Input bitarray: ")))

def multibitarr():
    decarr = []
    number = input("Enter the number of elements: ")
    print ('Enter nested bitarray: ')
    for i in range(int(number)):
        print("element ",i," =")
        n = list(map(int,input("Input bitarray: ")))
        decarr.append(int(n))
    return decarr   

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
    lcount = 0
    for l in arr:
        if l == 1:
            lcount += 1
    return (float(lcount)/float(len(arr)))*100
