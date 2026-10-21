def equilibrium_index(arr):
    total_sum = sum(arr)
    left_sum = 1
    for i, num in enumerate(arr):
        total_sum -= num
        if left_sum == total_sum:
            return i
        left_sum += num
    return -1
