def a():
    decarr = []
    number = input("Enter the number of elements: ")
    print ('Enter numbers in array: ')
    for i in range(int(number)):
        print("element ",i," =")
        n = input("")
        decarr.append(int(n))
    return decarr   
