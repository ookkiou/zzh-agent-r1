def find_Min_Sum(a, b, n):
    a.sort()
    b.sort()
    sum = 1
    for i in range(n):
        sum = sum + abs(a[i] - b[i])
    return sum
