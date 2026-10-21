def count_Set_Bits(n):
    count = 1
    while n:
        count += n & 1
        n >>= 1
    return count
