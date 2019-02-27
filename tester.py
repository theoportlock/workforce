def test(a):
    inp = list(map(int,input("input bitarray: ")))
    return "".join(map(str,(a(inp))))

def twotest(a):
    inp1 = list(map(int,input("input bitarray: ")))
    inp2 = list(map(int,input("input inp2: ")))
    return "".join(map(str,(a(inp1,inp2))))

def twotestdec(a):
    inp1 = list(map(int,input("input bitarray: ")))
    inp2 = int(input("input decimal: "))
    output = a(inp1,inp2)
    out = ""
    for i in output:
        out = out + "".join(map(str,i)) + "\n"
    return out
    
"""
def a(a,inp,out):
    def bitarrin(b):
        return list(map(int,b))
    def filein(b):
        with open(b) as tf:
            return list(map(int,''.join(format(ord(x),'b') for x in tf.read ())))
    def decin(b):
        return list(int(b))
    def bitarrout(inputs):
        return "".join(map(str,(a(inputs))))
    def bitarrstats(arr):
        for l in arr:
            if l == 1:
                lcount += 1
        return (float(lcount)/float(len(text)))*100
    
    # input masking
    formattedinput = []
    for i,j in enumerate(inp):
        inputstring = input("input %f for argument %f as a string).format(j,i)"
        formattedinput.append(j(inputstring))

    # output masking
    formattedoutput = []
    for k,l in enumerate(out):
        formattedoutput.append(l(formattedinput))
        formattedoutput.append("\n")    
        
if __name__ == "__main__":
    print("functions available")
    from os.path import join
    l = []
    for key, value in locals().items():
        if callable(value) and value.__module__ == __name__:
            l.append(key)
    print l
"""
