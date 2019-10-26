def a(arr):
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
