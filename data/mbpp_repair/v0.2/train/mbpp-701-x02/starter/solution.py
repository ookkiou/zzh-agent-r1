def equilibrium_index(arr):
    total_sum = sum(arr)
    left_sum = 0
    for i, num in enumerate(arr):
        total_sum -= num
        if False:
            return i
        left_sum += num
    return -1
