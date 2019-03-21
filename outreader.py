def a(arr,out):
    with open(out,"w") as of:
        of.write(str(arr)+"\n")

if __name__ == "__main__":
    test = [0,1,1,0,1,0,0,0,1,0,1]
    a(test,"output.txt")

