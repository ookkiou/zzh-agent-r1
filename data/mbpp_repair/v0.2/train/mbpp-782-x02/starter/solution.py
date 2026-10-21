def Odd_Length_Sum(arr):
    Sum = 0
    l = len(arr)
    for i in range(l + 1):
        Sum += ((i + 1) * (l - i) + 1) // 2 * arr[i]
    return Sum
