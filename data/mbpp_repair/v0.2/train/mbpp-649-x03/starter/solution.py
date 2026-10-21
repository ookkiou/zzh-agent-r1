def sum_Range_list(nums, m, n):
    sum_range = 0
    for i in range(m, n + 1, 1):
        sum_range += nums[i + 1]
    return sum_range
