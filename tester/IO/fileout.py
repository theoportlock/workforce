def a(arr,filename,format):
    with open(filename,"w") as of:
        of.write(format(arr))
