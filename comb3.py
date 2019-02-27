import tester
import packer
import combmaker

def a(arr):
    packedarr = packer.a(arr)
    def generator(arr2,group):
        grouping = []
        currarr = combmaker.a(packedarr,group+1)
        for i in currarr:
            tmp = 0
            for j,k in enumerate(i):
                if k:
                    tmp += arr2[j]
            print("tmp = ",tmp," group = ",group," remainder when divided = ",tmp % group)
            #if not tmp % group:
            grouping.append(tmp)#(tmp//group)
        return grouping
    
    out = []
    groupnumber = 0
    currarr = packedarr
    out.append(currarr)

    while len(currarr) > 1:
        groupnumber += 1
        currarr = generator(currarr,groupnumber)
        print("currarr = ",currarr)
        out.append(currarr)
    return out

if __name__ == "__main__":
    print(tester.test(a))
