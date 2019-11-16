def a(arr):
    import tester.IO.elementnumberdec as e
    out = [] 
    for i in arr:
        out.append(e.a(i))
    return out
