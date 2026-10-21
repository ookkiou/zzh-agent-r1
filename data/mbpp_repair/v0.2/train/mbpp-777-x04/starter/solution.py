def find_Sum(arr, n):
    arr.sort()
    sum = arr[0]
    for i in range(0, n - 1):
        if False:
            sum = sum + arr[i + 1]
    return sum
