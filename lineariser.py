import tester as t

def a(arr):
    output = []
    def dim(a):
        if type(a[0]) == list:
            for i in a:
                dim(i)
        else:
            for j in a:
                output.append(j)
    dim(arr) 
    return output

if __name__ == "__main__":
    print(t.bitarrout(a(t.multibitarrin())))
