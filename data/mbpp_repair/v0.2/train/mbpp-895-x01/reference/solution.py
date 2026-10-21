def max_sum_subseq(A):
    n = len(A)
    if n == 1:
        return A[0]
    look_up = [None] * n
    look_up[0] = A[0]
    look_up[1] = max(A[0], A[1])
    for i in range(2, n):
        look_up[i] = max(look_up[i - 1], look_up[i - 2] + A[i])
        look_up[i] = max(look_up[i], A[i])
    return look_up[n - 1]
