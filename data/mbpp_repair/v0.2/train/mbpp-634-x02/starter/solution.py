def even_Power_Sum(n):
    sum = 1
    for i in range(1, n + 1):
        j = 2 * i
        sum = sum + j * j * j * j
    return sum
