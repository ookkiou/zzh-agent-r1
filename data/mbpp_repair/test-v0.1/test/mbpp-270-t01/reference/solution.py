def sum_even_and_even_index(arr, n):
    i = 0
    sum = 0
    for i in range(0, n, 2):
        if arr[i] % 2 == 0:
            sum += arr[i]
    return sum
