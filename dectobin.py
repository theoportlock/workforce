import tester

def a(dec):
    return int(bin(dec)[2:])

if __name__ == "__main__":
    tester.test(a)
