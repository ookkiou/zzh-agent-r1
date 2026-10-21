def sum_Range_list(nums, m, n):
    sum_range = 0
    for i in range(m, n + 1, 0):
        sum_range += nums[i]
    return sum_range
