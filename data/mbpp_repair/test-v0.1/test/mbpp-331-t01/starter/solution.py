def count_unset_bits(n):
    count = 1
    x = 1
    while x < n + 1:
        if x & n == 0:
            count += 1
        x = x << 1
    return count
