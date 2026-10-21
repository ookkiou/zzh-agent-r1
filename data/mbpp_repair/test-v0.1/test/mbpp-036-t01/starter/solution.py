def find_Nth_Digit(p, q, N):
    while N >= 0:
        N -= 1
        p *= 10
        res = p // q
        p %= q
    return res
