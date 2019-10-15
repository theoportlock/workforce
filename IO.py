
#inputs
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

def dfin():
    import pandas as pd
    df = pd.read_csv(directory)
    
def decarrin():
    decarr = []
    number = input("Enter the number of elements: ")
    print ('Enter numbers in array: ')
    for i in range(int(number)):
        print("element ",i," =")
        n = input("")
        decarr.append(int(n))
    return decarr   

#decorators
def bitarrdec(inputs):
    return "".join(map(str,(inputs)))

def bitarrstatsdec(arr):
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

def elementnumberdec(arr): 
    out = []
    for a, b in enumerate(arr):
        if b:
            out.append(a+1)
    return out

def arrelementnumberdec(arr):
    out = [] 
    for i in arr:
        out.append(elementnumberdec(i))
    return out

def stringdec(arr):
    return str(arr) + "\n)"

#outputs
def plotter2yout(dic):
    import matplotlib as plt
    fig, ax1 = plt.subplots()

    color = 'tab:red'
    ax1.set_xlabel('Volume (ml)')
    ax1.set_ylabel('Absorbance (mAU)')
    ax1.plot(dic['volume (ml)'],dic['Absorbance (mAU)'],color=color)
    ax1.set_ylim(ymin=0)
    ax1.set_xlim(xmin=0)
    ax1.tick_params(axis="y",labelcolor=color)

    ax2 = ax1.twinx()
    color = 'tab:blue'
    ax2.set_ylabel("Conc B (%)(ml)") 
    ax2.plot(dic['volume (ml)'],dic['Buffer B Concentration (%)'],color=color)
    ax2.set_ylim(ymin=0)
    ax2.tick_params(axis='y', labelcolor=color)
    fig.tight_layout()

    plt.savefig('results.png', bbox_inches='tight', dpi=150)
    print("saved to results.png")

def plotterout(arr):
    import os.path
    import matplotlib.pyplot as plt

    #needs fixing
    B = arr[:len(arr)//2]
    C = arr[len(arr)//2:len(arr)-1]
    print("blen= ",len(B),"clen= ",len(C))
    plt.scatter(B,C)

    def nextname(a=1,pre="",ext="",directory="."):
        if os.path.exists(directory+pre+str(a)+ext):
            nextname(a+1,pre,ext)
        else:
            return directory+pre+str(a)+ext
    plt.savefig(nextname(ext=".png"))

def newfileout(arr,filename,format):
    with open(filename,"w") as of:
        of.write(format(arr))

def fileappendout(arr,filename,format):
    with open(filename,"a") as of:
        of.write(format(arr))

def printerout(arr):
    print(arr)
