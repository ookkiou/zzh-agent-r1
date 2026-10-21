def get_Number(n, k):
    arr = [0] * n
    i = 0
    odd = 1
    while odd <= n:
        arr[i] = odd
        i += 1
        odd += 2
    even = 2
    while even <= n:
        arr[i] = even
        i += 1
        even += 2
    return arr[k - 1]
