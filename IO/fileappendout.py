def a(arr,filename,format):
    with open(filename,"a") as of:
        of.write(format(arr))
