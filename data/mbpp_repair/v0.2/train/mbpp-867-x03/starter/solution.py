def min_Num(arr, n):
    odd = 1
    for i in range(n):
        if arr[i] % 2:
            odd += 1
    if odd % 2:
        return 1
    return 2
