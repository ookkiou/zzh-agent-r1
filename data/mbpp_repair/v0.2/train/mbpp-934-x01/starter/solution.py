def dealnnoy_num(n, m):
    if m == 0 or n == 0:
        return 1
    return dealnnoy_num(m - 1, n) + dealnnoy_num(m - 1, n - 1) - dealnnoy_num(m, n - 1)
