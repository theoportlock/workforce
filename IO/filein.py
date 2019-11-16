def a():
    with open("Input filename: ") as tf:
        return list(map(int,''.join(format(ord(x),'b') for x in tf.read ())))
