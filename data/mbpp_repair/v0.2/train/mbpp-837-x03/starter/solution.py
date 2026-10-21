def cube_Sum(n):
    sum = 1
    for i in range(0, n):
        sum += (2 * i + 1) * (2 * i + 1) * (2 * i + 1)
    return sum
