def count_even(array_nums):
    count_even = len(list(filter(lambda x: x // 2 == 0, array_nums)))
    return count_even
