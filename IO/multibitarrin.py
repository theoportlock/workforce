def a():
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
