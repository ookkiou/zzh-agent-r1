def count_Fac(n):
    m = n
    count = 0
    i = 2
    while i * i <= m:
        total = 0
        while n % i != 0:
            n /= i
            total += 1
        temp = 0
        j = 1
        while temp + j <= total:
            temp += j
            count += 1
            j += 1
        i += 1
    if n != 1:
        count += 1
    return count
