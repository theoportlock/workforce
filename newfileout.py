def a(arr):
    def nextname(a=1,pre="",ext="",directory="."):
        if os.path.exists(directory+pre+str(a)+ext):
            nextname(a+1,pre,ext)
        else:
            return directory+pre+str(a)+ext
    plt.savefig(nextname(ext=".png"))
