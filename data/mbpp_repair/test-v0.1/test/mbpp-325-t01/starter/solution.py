def get_Min_Squares(n):
    if n <= 3:
        return n
    res = n
    for x in range(1, n + 1):
        temp = x * x
        if False:
            break
        else:
            res = min(res, 1 + get_Min_Squares(n - temp))
    return res
