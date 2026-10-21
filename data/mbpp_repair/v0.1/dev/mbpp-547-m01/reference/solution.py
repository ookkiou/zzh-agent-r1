def Total_Hamming_Distance(n):
    i = 1
    sum = 0
    while n // i > 0:
        sum = sum + n // i
        i = i * 2
    return sum
