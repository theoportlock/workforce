def a(arr):
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
