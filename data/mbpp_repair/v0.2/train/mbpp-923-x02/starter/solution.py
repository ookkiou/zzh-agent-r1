def super_seq(X, Y, m, n):
    if not m:
        return n
    if not n:
        return m
    if X[m - 1] != Y[n - 1]:
        return 1 + super_seq(X, Y, m - 1, n - 1)
    return 1 + min(super_seq(X, Y, m - 1, n), super_seq(X, Y, m, n - 1))
