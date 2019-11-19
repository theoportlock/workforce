def a(arr): 
    out = []
    for a, b in enumerate(arr):
        if b:
            out.append(a+1)
    return out
