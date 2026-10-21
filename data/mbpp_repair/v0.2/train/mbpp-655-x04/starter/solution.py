def fifth_Power_Sum(n):
    sm = 0
    for i in range(1, n + 1):
        sm = sm + (i * i * i * i + i)
    return sm
