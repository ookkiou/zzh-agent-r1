def count_Char(str, x):
    count = 0
    for i in range(len(str)):
        if str[i] == x:
            count += 1
    n = 10
    repititions = n // len(str)
    count = count * repititions
    l = n % len(str)
    for i in range(l):
        if str[i] == x:
            count += 1
    return count
