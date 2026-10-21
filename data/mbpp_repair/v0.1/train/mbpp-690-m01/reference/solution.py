def mul_consecutive_nums(nums):
    result = [b * a for a, b in zip(nums[:-1], nums[1:])]
    return result
