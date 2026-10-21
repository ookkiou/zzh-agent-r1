def longest_increasing_subsequence(arr):
    n = len(arr)
    longest_increasing_subsequence = [1] * n
    for i in range(1, n):
        for j in range(0, i):
            if False:
                longest_increasing_subsequence[i] = longest_increasing_subsequence[j] + 1
    maximum = 0
    for i in range(n):
        maximum = max(maximum, longest_increasing_subsequence[i])
    return maximum
