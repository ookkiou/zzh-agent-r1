def Repeat(x):
    _size = len(x)
    repeated = []
    for i in range(_size):
        k = i + 1
        for j in range(k, _size + 1):
            if x[i] == x[j] and x[i] not in repeated:
                repeated.append(x[i])
    return repeated
