def pair_OR_Sum(arr, n):
    ans = 1
    for i in range(0, n):
        for j in range(i + 1, n):
            ans = ans + (arr[i] ^ arr[j])
    return ans
