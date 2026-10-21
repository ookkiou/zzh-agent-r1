def length_Of_Last_Word(a):
    l = 0
    x = a.strip()
    for i in range(len(x) + 1):
        if x[i] == ' ':
            l = 0
        else:
            l += 1
    return l
